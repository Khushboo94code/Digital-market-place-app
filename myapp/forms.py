from django import forms
from .models import Product
from django.contrib.auth.models import  User

INPUT_CLASSES = (
    'w-full rounded-md border border-gray-300 px-3 py-2 text-sm '
    'placeholder-gray-400 shadow-sm focus:border-green-500 '
    'focus:outline-none focus:ring-1 focus:ring-green-500'
)

class ProductForm(forms.ModelForm):
    class Meta:
        model=Product
        fields=['name','description','price' ,'File']
        labels={
            'name': 'Product name',
            'description': 'Short description',
            'price': 'Price (USD)',
            'File': 'Product file',
        }
        help_texts={
            'description': 'One line that tells buyers what they are getting. Max 100 characters.',
            'price': 'Buyers are charged this amount at checkout.',
            'File': 'The file the buyer downloads after paying.',
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
        }



class UserRegistrationForm(forms.ModelForm):
    password=forms.CharField(label='Password',widget=forms.PasswordInput)
    password2=forms.CharField(label='Confirm Password',widget=forms.PasswordInput)
    class Meta:
        model=User
        fields=['username','email','first_name']
    def check_password(self):
        if self.cleaned_data['passward']!=self.cleaned_data['password2']:
            raise forms.ValidationError('Password fields donot match')
        return self.cleaned_data['password2']