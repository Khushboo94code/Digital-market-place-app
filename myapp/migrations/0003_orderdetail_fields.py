from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0002_orderdetail'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderdetail',
            name='customer_email',
            field=models.EmailField(default='', max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='orderdetail',
            name='amount',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='orderdetail',
            name='stripe_checkout_session_id',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='orderdetail',
            name='stripe_payment_intent',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='orderdetail',
            name='updated_on',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
