from django import forms
from .models import Product
from django.contrib.auth.models import  User

INPUT_CLASSES = (
    'w-full rounded-md border border-gray-300 px-3 py-2 text-sm '
    'placeholder-gray-400 shadow-sm focus:border-green-500 '
    'focus:outline-none focus:ring-1 focus:ring-green-500'
)

class ProductForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Both fields take a file, so it was easy to put the cover art in
        # 'Product file' and leave 'Cover image' empty. That saved without
        # complaint, then the storefront showed a grey "No image" box and the
        # picture sat in the paid-downloads area where nothing serves it.
        # Requiring it here turns that silent mistake into a visible error.
        #
        # Form-level only: Product.image stays blank=True, so products saved
        # before this and anything created in the admin remain valid. An edit of
        # a product that already has a cover does not ask for it again — Django's
        # FileField falls back to the stored value when no new file is sent.
        self.fields['image'].required = True

    class Meta:
        model=Product
        fields=['name','description','price' ,'File','image']
        labels={
            'name': 'Product name',
            'description': 'Short description',
            'price': 'Price (USD)',
            'File': 'Product file \u2014 what buyers download',
            'image': 'Cover image \u2014 what buyers see',
        }
        help_texts={
            'description': 'One line that tells buyers what they are getting. Max 100 characters.',
            'price': 'Buyers are charged this amount at checkout.',
            'File': (
                'The file the buyer receives after paying. Never shown publicly, '
                'so it is not used as the picture on the storefront.'
            ),
            'image': (
                'The picture shown on the storefront and the product page. '
                'A square image looks best.'
            ),
        }
        widgets={
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'e.g. Lightroom Presets Pack',
            }),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'e.g. 20 film-inspired presets for portrait photography',
            }),
            'price': forms.NumberInput(attrs={
                'class': INPUT_CLASSES + ' pl-7',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
            'File': forms.ClearableFileInput(attrs={
                'class': (
                    'block w-full cursor-pointer text-sm text-gray-600 '
                    'file:mr-4 file:cursor-pointer file:rounded-md file:border-0 '
                    'file:bg-green-50 file:px-4 file:py-2 file:text-sm '
                    'file:font-medium file:text-green-700 hover:file:bg-green-100'
                ),
            }),
            'image': forms.ClearableFileInput(attrs={
                'accept': 'image/*',
                'class': (
                    'block w-full cursor-pointer text-sm text-gray-600 '
                    'file:mr-4 file:cursor-pointer file:rounded-md file:border-0 '
                    'file:bg-green-50 file:px-4 file:py-2 file:text-sm '
                    'file:font-medium file:text-green-700 hover:file:bg-green-100'
                ),
            }),
        }



class UserRegistrationForm(forms.ModelForm):
    password=forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder':'At least 8 characters'}),
    )
    password2=forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'placeholder':'Type the same password again'}),
    )

    # Declared here to override the model, where email is blank=True and would
    # therefore be optional. One email must identify one account, so it has to
    # be filled in. The placeholder spells out the format, since a seller cannot
    # reuse the email already on their buyer account.
    email=forms.EmailField(
        label='Email',
        required=True,
        # Kept short: a long placeholder is clipped by the input's width, which
        # hides the end of it. The seller note lives under the field instead.
        widget=forms.EmailInput(attrs={'placeholder':'you@example.com'}),
    )

    # A ChoiceField only ever validates to one of these two values, so the
    # browser can say which button was picked without being able to name a
    # group. The view decides what 'seller' means.
    ROLE_CHOICES=[
        ('buyer','I want to buy'),
        ('seller','I want to sell'),
    ]
    role=forms.ChoiceField(
        label='What brings you here?',
        choices=ROLE_CHOICES,
        initial='buyer',
        widget=forms.RadioSelect,
    )

    class Meta:
        model=User
        fields=['username','email','first_name']
        widgets={
            'username':forms.TextInput(attrs={'placeholder':'e.g. muskan_store'}),
            'first_name':forms.TextInput(attrs={'placeholder':'e.g. Muskan'}),
        }
    def clean_password2(self):
        if self.cleaned_data.get('password')!=self.cleaned_data['password2']:
            raise forms.ValidationError('Password fields donot match')
        return self.cleaned_data['password2']

    def clean_email(self):
        # One email, one account — so a buyer and a seller account need separate
        # addresses. Compared case-insensitively because 'A@x.com' and 'a@x.com'
        # are the same mailbox, and purchases are matched by email.
        email=self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account already uses this email. Use a different email for '
                'your seller account.'
            )
        return email