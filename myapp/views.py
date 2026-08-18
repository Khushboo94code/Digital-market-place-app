import os
import time

from django.shortcuts import render, get_object_or_404, redirect
from .models import Product,orderDetail
from django.conf import settings
from django.urls import reverse
import stripe,json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse,HttpResponseNotFound,FileResponse
from .forms import ProductForm,UserRegistrationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from .roles import is_seller, SELLER_GROUP
from django.db import transaction
from django.db.models import F,Sum,Q
import datetime
from django.utils import timezone

# stripe.api_key is a module-level global shared by every thread. Set it once at
# import instead of inside each view, so concurrent requests can't reassign it
# while another request is mid-call.
stripe.api_key = settings.STRIPE_SECRET_KEY


# Create your views here.
def index(request):
    products = Product.objects.all()
    return render(request, 'myapp/index.html', {'products': products})

def detail(request,id):
    # Public on purpose: buyers browse before they have an account. The Buy
    # button in the template is what asks anonymous visitors to log in.
    product=get_object_or_404(Product,id=id)
    stripe_publishable_key=settings.STRIPE_PUBLISHABLE_KEY
    return render(request,'myapp/detail.html',{'product':product , 'stripe_publishable_key': stripe_publishable_key})


@csrf_exempt
def create_checkout_session(request, id):
    request_data = json.loads(request.body)
    product = Product.objects.get(id=id)

    checkout_session = stripe.checkout.Session.create(
        customer_email=request_data['email'],

        payment_method_types=['card'],

        line_items=[
            {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name
                    },
                    'unit_amount': int(product.price * 100)
                },
                'quantity': 1,
            }
        ],

        mode="payment",

        success_url=request.build_absolute_uri(
            reverse('success')
        ) + "?session_id={CHECKOUT_SESSION_ID}",

        cancel_url=request.build_absolute_uri(
            reverse('failed')
        ),
    )
    order=orderDetail()
    order.customer_email=request_data['email']
    order.product=product
    order.stripe_checkout_session_id=checkout_session.id
    order.amount=int(product.price)
    order.save()

    return JsonResponse({'sessionId':checkout_session.id,'url':checkout_session.url})



def payment_success_view(request):
    session_id=request.GET.get('session_id')
    if session_id is None:
        return HttpResponseNotFound()
    session=stripe.checkout.Session.retrieve(session_id)
    order = get_object_or_404(orderDetail,stripe_checkout_session_id=session_id)

    # Only count the sale the first time; the buyer may refresh this page.
    # Read-then-save would double-count once concurrent workers are in play, so
    # claim the order with a single conditional UPDATE and let the database
    # decide the winner. claimed is the row count, so exactly one caller gets 1.
    with transaction.atomic():
        claimed = orderDetail.objects.filter(pk=order.pk,has_paid=False).update(
            stripe_payment_intent=session.payment_intent or '',
            has_paid=True,
            updated_on=timezone.now(),  # .update() skips auto_now
        )
        if claimed:
            Product.objects.filter(id=order.product_id).update(
                total_sales=F('total_sales')+1,
                total_sales_amount=F('total_sales_amount')+order.amount,
            )

    order.refresh_from_db()
    return render (request,'myapp/payment_success.html',{'order':order})

def payment_failed_view(request):
    return render (request,'myapp/failed.html')


@login_required
def create_product(request):
    if not is_seller(request.user):
        return redirect('invalid')
    if request.method=='POST':
        product_form=ProductForm(request.POST,request.FILES)
        if product_form.is_valid():
            new_product=product_form.save(commit=False)
            new_product.seller=request.user
            new_product.save()
            return redirect('index')
    else:
        product_form=ProductForm()
    return render (request,'myapp/create_product.html',{'product_form':product_form})



@login_required
def product_edit(request,id):
    if not is_seller(request.user):
        return redirect('invalid')
    product=Product.objects.get(id=id)
    # is_seller says "you may sell"; this says "you may edit THIS product".
    if product.seller != request.user:
        return redirect('invalid')
    product_form=ProductForm(request.POST or None,request.FILES or None,instance=product)
    if request.method=='POST':
        if product_form.is_valid():
            product_form.save()
            return redirect('index')

    return render (request,'myapp/product_edit.html',{'product_form':product_form,'product':product})




@login_required
def product_delete(request,id):
    if not is_seller(request.user):
        return redirect('invalid')
    product=Product.objects.get(id=id)
    if product.seller != request.user:
            return redirect('invalid')
    if request.method=='POST':
        product.delete()
        return redirect('index')
    return render (request,'myapp/delete.html',{'product':product})

@login_required
def dashboard(request):
    # login_required only asks "are you logged in?" — a buyer passes that. This
    # is the check that keeps buyers out of the seller area.
    if not is_seller(request.user):
        return redirect('invalid')
    products=Product.objects.filter(seller=request.user)
    print("request started")
    time.sleep(2)  # Give the database a moment to catch up with any recent sales
    print("request completed")
    return render(request,'myapp/dashboard.html',{'products':products})


def register(request):
    if request.method == 'POST':
        user_form=UserRegistrationForm(request.POST)
        if user_form.is_valid():
            new_user=user_form.save(commit=False)
            new_user.set_password(user_form.cleaned_data['password'])
            new_user.save()
            # The form can only ever hand back 'buyer' or 'seller'. The server
            # maps that to a group name — the browser never sends one.
            wants_to_sell=user_form.cleaned_data['role']=='seller'
            if wants_to_sell:
                seller_group,_=Group.objects.get_or_create(name=SELLER_GROUP)
                new_user.groups.add(seller_group)

            # Log the new account in, replacing whoever was signed in before.
            # Without this the previous session survives, so registering a buyer
            # while signed in as a seller leaves you browsing as the seller.
            login(request,new_user)

            # They just told us what they came for, so send them there. This is
            # a one-off after signup, not a role-based redirect on every login.
            # Dashboard rather than the product form: it greets them with an
            # empty state they can read, instead of dropping them into a form
            # they never asked for.
            return redirect('dashboard' if wants_to_sell else 'index')
    else:
        user_form=UserRegistrationForm()
    return render(request,'myapp/register.html',{'user_form':user_form})


def logout_view(request):
    logout(request)
    return render(request,'myapp/logout.html')

def invalid(request):
    return render(request,'myapp/invalid.html')


def choose_role(request):
    # Deliberately open to anonymous visitors: this is the front door, and the
    # Sell card is what sends them into login when they pick it.
    return render(request,'myapp/choose_role.html')


@login_required
def become_seller(request):
    # Seller access is decided at registration, not upgraded later. A buyer who
    # lands here is only told they need a seller account — there is deliberately
    # no code path that grants the role to an existing buyer, so no click can
    # promote anyone by accident.
    if is_seller(request.user):
        return redirect('dashboard')

    return render(request,'myapp/become_seller.html')

@login_required
@login_required
def download(request, id):
    """Serve a purchased file, after checking the caller actually paid for it.

    The download links used to point straight at /media/uploads/<name>, which
    Django handed to anyone holding the URL — no login, no order, no payment.
    One shared link or one search-engine crawl gave the file away for free.

    MEDIA_ROOT/uploads is no longer routed over HTTP at all (see mysite/urls.py),
    so this view is the only way to reach a product file.
    """
    product = get_object_or_404(Product, id=id)

    # iexact for the same reason mypurchases uses it: the buyer types their email
    # at Stripe checkout, so its case need not match the one on their account.
    bought = orderDetail.objects.filter(
        product=product,
        has_paid=True,
        customer_email__iexact=request.user.email,
    ).exists()

    # A seller can always fetch their own upload, otherwise they cannot check
    # what their buyers actually receive.
    if not (bought or product.seller_id == request.user.id):
        return redirect('invalid')

    # FileResponse streams the file in chunks instead of reading it into memory,
    # and closes the handle once the response is finished.
    return FileResponse(
        product.File.open('rb'),
        as_attachment=True,
        filename=os.path.basename(product.File.name),
    )


def mypurchases(request):
    # Without login_required this raised AttributeError: AnonymousUser has no
    # .email. iexact rather than exact because the buyer types their email at
    # Stripe checkout — 'Muski@gmail.com' and 'muski@gmail.com' are the same person.
    orders=orderDetail.objects.filter(customer_email__iexact=request.user.email,has_paid=True)
    return render(request,'myapp/purchases.html',{'orders':orders})
@login_required
def sales(request):
    if not is_seller(request.user):
        return redirect('invalid')
    orders=orderDetail.objects.filter(product__seller=request.user,has_paid=True)

    total_sales=orders.aggregate(Sum('amount',default=0))
    last_year=timezone.now()-datetime.timedelta(days=365)

    orders=orderDetail.objects.filter(product__seller=request.user,has_paid=True,created_on__gte=last_year)
    yearly_sales=orders.aggregate(Sum('amount',default=0))



    last_month=timezone.now()-datetime.timedelta(days=30)
    
    orders=orderDetail.objects.filter(product__seller=request.user,has_paid=True,created_on__gte=last_month)
    monthly_sales=orders.aggregate(Sum('amount',default=0))

    last_week=timezone.now()-datetime.timedelta(days=7)
    
    orders=orderDetail.objects.filter(product__seller=request.user,has_paid=True,created_on__gte=last_week)
    weekly_sales=orders.aggregate(Sum('amount',default=0))



    daily_sales_sum=(orderDetail.objects
        .filter(product__seller=request.user,has_paid=True)
        .values('created_on__date')
        .annotate(sum=Sum('amount'))
        .order_by('created_on__date'))
    print(daily_sales_sum)

    product_sales_sum=(Product.objects
        .filter(seller=request.user)
        .annotate(sum=Sum('orderdetail__amount',filter=Q(orderdetail__has_paid=True),default=0))
        .order_by('-sum'))

    # Chart.js reads these through {{ ...|json_script }}, so keep them plain lists.
    daily_chart={
        'labels':[d['created_on__date'].strftime('%d %b') for d in daily_sales_sum],
        'values':[d['sum'] for d in daily_sales_sum],
    }
    product_chart={
        'labels':[p.name for p in product_sales_sum],
        'values':[p.sum for p in product_sales_sum],
    }

    return render(request,'myapp/sales.html',{'total_sales':total_sales,'yearly_sales':yearly_sales,'monthly_sales':monthly_sales,'weekly_sales':weekly_sales,'daily_sales_sum':daily_sales_sum,'product_sales_sum':product_sales_sum,'daily_chart':daily_chart,'product_chart':product_chart})




    
