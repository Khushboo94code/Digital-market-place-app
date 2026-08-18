# Buyer / Seller roles — build guide

A simple, step-by-step guide. Do one step. Check it works. Then do the next one.

---

## What we are building

1. A page that asks: **do you want to buy, or sell?**
2. A **buyer** sees only buyer pages (shop, product page, my purchases).
3. A **seller** sees the seller pages **too** (dashboard, sales, new product).

## The one rule to remember

**A seller is also a buyer.**

A seller sells their own products, but they may also want to buy someone else's.
So selling is something we **add** to an account. It is not a different account.

| | Shop, product page, My Purchases | Dashboard, Sales, New Product |
|---|---|---|
| Buyer | yes | no |
| Seller | yes | **yes** |

This means we never write `if seller ... else buyer`. We write:

```django
{% if user.is_authenticated %}
    <a href="{% url 'purchases' %}">My Purchases</a>   {# everybody #}

    {% if is_seller %}
        <a href="{% url 'dashboard' %}">Dashboard</a>  {# sellers get this EXTRA #}
    {% endif %}
{% endif %}
```

The seller part goes **inside**, as an extra. Never in an `{% else %}`.

## Two words that sound the same but are not

| Word | It asks | Do we have it? |
|---|---|---|
| **Authentication** | Who are you? | Yes — login, register, `@login_required` |
| **Authorization** | What are you allowed to open? | No — this is what we build |

`@login_required` only checks *"are you logged in?"*.
A buyer **is** logged in. So it can never stop a buyer from opening the seller
pages. We need a role check for that.

## What we chose, and why

We will use **Django Groups**.

A "Group" in Django is just a named role. We make one group called `Seller`.
A user who is in that group is a seller. A user who is not, is a buyer.

Why Groups:

- The tables already exist in your database (`auth_group`, `auth_user_groups`).
  Both are empty right now. We only add rows.
- No new model to write.
- We can **save** the answer when a user says "I want to sell".

Why not "a seller is anyone who owns a product":
that idea is simpler, but a new seller owns nothing yet — so they could never
create their first product. And if a seller deletes their last product, they
would stop being a seller by accident.

---

# Step 1 — Make the Seller group (by hand, in the admin)

The rule from here on is simple:

> **You are a seller if you are in the Seller group.**

Right now that group does not exist and nobody is in it. So we create it and add
the people who are already selling. No code, no migration — just clicking.

Start the admin:

```bash
../env/bin/python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ and log in as `admin`.

**1. Create the group**

- Click **Groups** → **Add group**
- Name: `Seller`
- Leave permissions empty (we do our own checks)
- Save

**2. Add the users who already sell**

- Click **Users**
- Open each of `admin`, `Muskan`, `Aarti`
- Scroll to **Groups**, pick `Seller`, save

Why these three: they already own products. If we skip this, they lose their own
dashboard the moment Step 5 adds the gate. `khushboo` owns nothing, so leave her
out — she is a buyer.

**Check:** the Seller group has exactly those 3 users.

> **This step is only about users who already exist.**
> Every new seller after today gets the role from the `/sell/` page in **Step 4**,
> automatically. You never do this by hand again.

---

# Step 2 — One place that answers "is this user a seller?"

Do not copy the same check into ten files. Write it once.

New file `myapp/roles.py`:

```python
def is_seller(user):
    return user.is_authenticated and user.groups.filter(name='Seller').exists()
```

Now templates also need it. New file `myapp/context_processors.py`:

```python
from .roles import is_seller as user_is_seller


def roles(request):
    # makes {{ is_seller }} available in EVERY template
    return {'is_seller': user_is_seller(request.user)}
```

Turn it on in `mysite/settings.py`, inside `TEMPLATES` → `OPTIONS` →
`context_processors`, add this line at the end of the list:

```python
'myapp.context_processors.roles',
```

**Check:** put `{{ is_seller }}` in any template. It shows `True` or `False`.

---

# Step 3 — The "buy or sell?" page

This is the nice-looking page you wanted.

In `myapp/views.py`:

```python
def choose_role(request):
    return render(request, 'myapp/choose_role.html')
```

In `myapp/urls.py`:

```python
path('start/', views.choose_role, name='choose_role'),
```

New template `myapp/templates/myapp/choose_role.html` — two big cards:

- **I want to buy** → links to `{% url 'index' %}`
- **I want to sell** → links to `{% url 'become_seller' %}`

Write a friendly line under the seller card, for example:
*"You can still buy things too."*
This keeps the page honest — it is a starting point, not a locked choice.

**Check:** open `/start/`. Both cards are clickable.

> Note: the seller card will break until Step 4 adds that URL. Do Step 4 next,
> or leave the link out for now. A `{% url %}` for a URL that does not exist
> crashes **every** page, because every template extends `base.html`.

---

# Step 4 — The page that makes someone a seller

In `myapp/views.py`:

```python
from django.contrib.auth.models import Group
from .roles import is_seller


@login_required
def become_seller(request):
    if is_seller(request.user):
        return redirect('dashboard')          # already a seller

    if request.method == 'POST':
        group, _ = Group.objects.get_or_create(name='Seller')
        request.user.groups.add(group)        # <- this one row makes them a seller
        return redirect('dashboard')

    return render(request, 'myapp/become_seller.html')
```

In `myapp/urls.py`:

```python
path('sell/', views.become_seller, name='become_seller'),
```

New template `myapp/templates/myapp/become_seller.html`:

```django
{% extends 'myapp/base.html' %}

{% block body %}
<div class="mx-auto max-w-xl p-10">
    <h1 class="mb-4 text-3xl font-bold">Start selling</h1>
    <p class="mb-6 text-gray-600">
        List your products and reach buyers. You keep your buyer account, so you
        can still shop as normal.
    </p>

    <form method="POST">
        {% csrf_token %}
        <button type="submit" class="rounded-md bg-green-500 px-4 py-2 text-white">
            Start selling
        </button>
    </form>
</div>
{% endblock %}
```

Two things worth understanding here:

- **`@login_required` does the hard work.** A visitor who is not logged in gets
  sent to `/login/?next=/sell/`. After they log in, Django reads `next=` and
  brings them straight back. You do not write any of that.
- **We use a form (POST), not a link.** A link is a GET. Browsers and link
  preview bots open GET links on their own. Someone could become a seller by
  accident. Anything that **changes** data must be a POST.

**Check:** log in as a buyer, click through, and you land on the dashboard.

---

# Step 5 — Lock the seller pages

Right now any logged-in user can open `/dashboard/`. Fix that.

In `myapp/views.py`:

```python
from django.contrib.auth.decorators import user_passes_test
from .roles import is_seller

seller_required = user_passes_test(is_seller, login_url='invalid')
```

Then put it on the seller views (keep `@login_required` above it):

```python
@login_required
@seller_required
def dashboard(request):
    ...
```

Do the same for `sales`, `create_product`, `product_edit`, `product_delete`.

**Check:** a buyer opening `/dashboard/` is sent away. A seller is not.

---

# Step 6 — Fix the navbar

The gate is on, but buyers still **see** the links. They just get bounced.
That is confusing. Hide them.

Open `myapp/templates/myapp/base.html`. Today there is one block:

```django
{% if user.is_authenticated %}
    Dashboard   Sales   Orders   New Product     ← seller links
    My Purchases                                 ← buyer link
    username   Logout
{% else %}
    Login   Register
{% endif %}
```

One condition controls everything, so buyers get the seller links too.

Split it into **two** blocks:

```django
{% if is_seller %}
    Dashboard   Sales   Orders   New Product
{% endif %}

{% if user.is_authenticated %}
    My Purchases
    {% if not is_seller %}  Sell  {% endif %}
    username   Logout
{% else %}
    Sell   Login   Register
{% endif %}
```

Nothing is deleted. The same links are just grouped differently. Sellers pass
**both** blocks, so they get everything — that is the additive rule working.

**Check:**

| Logged in as | Should see |
|---|---|
| nobody | Sell, Login, Register |
| buyer | My Purchases, Sell, Logout |
| seller | Dashboard, Sales, Orders, New Product, My Purchases, Logout |

---

# Step 7 — Finish the buyer side

The seller side is in good shape. The buyer side still has real problems.

**a. Let people browse without an account.**
`detail` has `@login_required` on it. So a visitor sees the shop but hits a login
wall on any product. Remove that decorator and ask for login at the **Buy**
button instead.

This also fixes a confusing bug: `detail.html` reads the buyer's email from
`{{ request.user.email }}` in a hidden div. For a logged-out visitor that div is
empty, so the JavaScript stops and shows *"please enter your email address"* —
but the page has no box to type an email into.

**b. `mypurchases` has no `@login_required`.**
A logged-out visitor gets a 500 error, because `AnonymousUser` has no `.email`.

**c. Purchases are matched by email text, and case matters.**
`Muski@gmail.com` finds the order. `muski@gmail.com` finds nothing. If a buyer
types their email a little differently at checkout, their purchases disappear
forever. Either always save the email in lower case, or add a `customer` link
(ForeignKey to User) on `orderDetail`.

**d. `dashboard` shows a blank page** when a seller has no products yet. Add an
"empty state" — a short line and a button to add the first product.

---

## Two mistakes that are easy to make

1. **Do Step 1 before Step 5.** If you lock the pages before marking your
   existing sellers, they lose access to their own products.

2. **Add the URL before the link.** If `base.html` has `{% url 'become_seller' %}`
   and that URL does not exist yet, **every page** in the site crashes with
   `NoReverseMatch` — because every template extends `base.html`.
