from django import forms
from .models import Issuer, TopIssuer


def get_issuer_choices(use_top_issuers=False):
    if use_top_issuers:
        issuers = sorted([top.issuer.code for top in TopIssuer.objects.select_related('issuer').all()])
        return [(issuer, issuer) for issuer in issuers]
    else:
        issuers = Issuer.objects.all()
        return [(issuer.code, issuer.code) for issuer in issuers]


class BaseIssuerFormMixin:
    def apply_common_styles_and_labels(self, lang_data, label_keys):
        for field_name, field in self.fields.items():
            # Apply Bootstrap classes
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-select' if field_name == 'issuer' else 'form-control'
                # if field_name != 'issuer':
                #     field.widget.attrs['id'] = 'date-input'

            # Assign labels using lang_data
            label_key = label_keys.get(field_name)
            if label_key:
                field.label = lang_data[label_key]

class DateRangeForm(forms.Form, BaseIssuerFormMixin):
    issuer = forms.ChoiceField(choices=get_issuer_choices())
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        lang_data = kwargs.pop('lang_data', {})
        super().__init__(*args, **kwargs)
        self.apply_common_styles_and_labels(lang_data, {
            'issuer': 'form_select',
            'start_date': 'form_from_date',
            'end_date': 'form_to_date',
        })

class TechnicalForm(forms.Form, BaseIssuerFormMixin):
    issuer = forms.ChoiceField(choices=get_issuer_choices(use_top_issuers=True))
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        lang_data = kwargs.pop('lang_data', {})
        super().__init__(*args, **kwargs)
        self.apply_common_styles_and_labels(lang_data, {
            'issuer': 'form_select',
            'start_date': 'form_from_date',
            'end_date': 'form_to_date',
        })

class FundamentalForm(forms.Form, BaseIssuerFormMixin):
    issuer = forms.ChoiceField(choices=get_issuer_choices(use_top_issuers=True))

    def __init__(self, *args, **kwargs):
        lang_data = kwargs.pop('lang_data', {})
        super().__init__(*args, **kwargs)
        self.apply_common_styles_and_labels(lang_data, {
            'issuer': 'form_select',
        })

class PredictionForm(forms.Form, BaseIssuerFormMixin):
    issuer = forms.ChoiceField(choices=get_issuer_choices(use_top_issuers=True))
    def __init__(self, *args, **kwargs):
        lang_data = kwargs.pop('lang_data', {})
        super().__init__(*args, **kwargs)
        self.apply_common_styles_and_labels(lang_data, {
            'issuer': 'form_select',
        })
