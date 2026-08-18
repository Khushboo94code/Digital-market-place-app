import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Product, orderDetail

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class DownloadAccessTests(TestCase):
    """A product file must reach paying buyers and nobody else.

    Before myapp.views.download existed these links pointed at
    /media/uploads/<name>, which Django served to any caller. These tests pin the
    replacement shut so it cannot regress back to a public URL.
    """

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.seller = User.objects.create_user(
            'seller', 'seller@example.com', 'pw-for-tests-1'
        )
        self.buyer = User.objects.create_user(
            'buyer', 'buyer@example.com', 'pw-for-tests-2'
        )
        self.stranger = User.objects.create_user(
            'stranger', 'stranger@example.com', 'pw-for-tests-3'
        )

        self.product = Product.objects.create(
            seller=self.seller,
            name='Test product',
            description='A thing',
            price=9.99,
            File=SimpleUploadedFile('secret.txt', b'paid-content-only'),
        )
        self.url = reverse('download', args=[self.product.id])

    def _paid_order(self, email):
        return orderDetail.objects.create(
            customer_email=email, product=self.product, amount=10, has_paid=True
        )

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_logged_in_stranger_is_refused(self):
        self.client.force_login(self.stranger)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('invalid'))

    def test_unpaid_order_is_refused(self):
        orderDetail.objects.create(
            customer_email=self.buyer.email,
            product=self.product,
            amount=10,
            has_paid=False,
        )
        self.client.force_login(self.buyer)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('invalid'))

    def test_paying_buyer_gets_the_file(self):
        self._paid_order(self.buyer.email)
        self.client.force_login(self.buyer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'paid-content-only')

    def test_email_case_does_not_matter(self):
        # The buyer types their email at Stripe checkout, so its case need not
        # match the address on their account.
        self._paid_order('BUYER@Example.COM')
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_seller_can_fetch_their_own_upload(self):
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_buying_one_product_does_not_unlock_another(self):
        other = Product.objects.create(
            seller=self.seller,
            name='Other product',
            description='Another thing',
            price=1.0,
            File=SimpleUploadedFile('other.txt', b'different-content'),
        )
        self._paid_order(self.buyer.email)  # paid for self.product only
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('download', args=[other.id]))
        self.assertRedirects(response, reverse('invalid'))


@override_settings(MEDIA_ROOT=MEDIA, DEBUG=False)
class MediaRoutingTests(TestCase):
    """Cover images stay public; uploads must not be routed over HTTP at all."""

    def test_uploads_prefix_is_not_served(self):
        response = self.client.get('/media/uploads/secret.txt')
        self.assertEqual(response.status_code, 404)

    def test_images_prefix_is_routed(self):
        # 404 because no such file exists, but the URL must resolve rather than
        # fall through as an unmatched pattern.
        response = self.client.get('/media/images/nope.jpg')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.resolver_match.view_name, 'django.views.static.serve')


@override_settings(MEDIA_ROOT=MEDIA)
class ProductFormCoverImageTests(TestCase):
    """The cover image must be supplied, and must not be confused with the file.

    Leaving it blank used to save quietly, put nothing on the storefront, and
    leave sellers hunting for a picture that was actually sitting in the
    paid-downloads area under the wrong field.
    """

    def setUp(self):
        self.seller = User.objects.create_user(
            'seller2', 'seller2@example.com', 'pw-for-tests-4'
        )

    @staticmethod
    def _fields():
        return {'name': 'Thing', 'description': 'A thing', 'price': '5.00'}

    @staticmethod
    def _png():
        # Smallest valid PNG, so ImageField's Pillow check passes.
        return SimpleUploadedFile(
            'cover.png',
            (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
                b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00'
                b'\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
            ),
            content_type='image/png',
        )

    def test_cover_image_is_required(self):
        from .forms import ProductForm

        form = ProductForm(
            data=self._fields(),
            files={'File': SimpleUploadedFile('product.zip', b'payload')},
        )
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_valid_with_both_files(self):
        from .forms import ProductForm

        form = ProductForm(
            data=self._fields(),
            files={
                'File': SimpleUploadedFile('product.zip', b'payload'),
                'image': self._png(),
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_keeps_an_existing_cover_without_reupload(self):
        from .forms import ProductForm

        product = Product.objects.create(
            seller=self.seller,
            name='Thing',
            description='A thing',
            price=5.0,
            File=SimpleUploadedFile('product.zip', b'payload'),
            image=self._png(),
        )
        form = ProductForm(data=self._fields(), files={}, instance=product)
        self.assertTrue(form.is_valid(), form.errors)

    def test_editing_a_product_with_no_cover_demands_one(self):
        from .forms import ProductForm

        product = Product.objects.create(
            seller=self.seller,
            name='Thing',
            description='A thing',
            price=5.0,
            File=SimpleUploadedFile('product.zip', b'payload'),
        )
        form = ProductForm(data=self._fields(), files={}, instance=product)
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_the_two_uploads_land_in_separate_directories(self):
        product = Product.objects.create(
            seller=self.seller,
            name='Thing',
            description='A thing',
            price=5.0,
            File=SimpleUploadedFile('product.zip', b'payload'),
            image=self._png(),
        )
        # uploads/ is served only through the paid-download view; images/ is public.
        self.assertTrue(product.File.name.startswith('uploads/'))
        self.assertTrue(product.image.name.startswith('images/'))
