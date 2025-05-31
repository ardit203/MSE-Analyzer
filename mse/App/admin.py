from django.contrib import admin
from .models import *

class IssuerAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'dashed']



class TopIssuerAdmin(admin.ModelAdmin):
    list_display = ['issuer',]

class StockAdmin(admin.ModelAdmin):
    list_display = ['code', 'date', 'price']
    list_filter = ['issuer__code']  # Use double underscores for related model field

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'

class LastDateAdmin(admin.ModelAdmin):
    list_display = ['code', 'date']

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'


class NewsAdmin(admin.ModelAdmin):
    list_display = ['code', 'date', 'document_id', 'title_en']
    list_filter = ['issuer__code']
    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'

class NewsAttachmentsAdmin(admin.ModelAdmin):
    list_display = ['code', 'document_id', 'type', 'file_name_en']
    list_filter = ['new__issuer__code']


    def code(self, obj):
        return obj.new.issuer.code

    code.short_description = 'Code'

    def document_id(self, obj):
        return obj.new.document_id

    document_id.short_description = 'Document Id'

class TechnicalAdmin(admin.ModelAdmin):
    list_display = ['code', 'date', 'indicator_type', 'timeframe', 'value', 'price', 'signal']
    list_filter = ['timeframe', 'indicator_type', 'issuer__code',]

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'

class FundamentalAdmin(admin.ModelAdmin):
    list_display = ['code', 'label', 'score']
    list_filter = ['issuer__code']  # Use double underscores for related model field

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'

class PredictionAdmin(admin.ModelAdmin):
    list_display = ['code', 'date', 'predicted_price']
    list_filter = ['issuer__code']  # Use double underscores for related model field

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'


class LastPredictionDateAdmin(admin.ModelAdmin):
    list_display = ['code', 'date']

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'



class MetricsAdmin(admin.ModelAdmin):
    list_display = ['code', 'r2_score', 'mse', 'mae', 'mape']
    list_filter = ['issuer__code']  # Use double underscores for related model field

    def code(self, obj):
        return obj.issuer.code

    code.short_description = 'Code'

admin.site.register(Issuer, IssuerAdmin)
admin.site.register(TopIssuer, TopIssuerAdmin)
admin.site.register(Stock, StockAdmin)
admin.site.register(LastDate,LastDateAdmin)
admin.site.register(New, NewsAdmin)
admin.site.register(TechnicalIndicator, TechnicalAdmin)
admin.site.register(Fundamental, FundamentalAdmin)
admin.site.register(Prediction, PredictionAdmin)
admin.site.register(LastPredictionDate, LastPredictionDateAdmin)
admin.site.register(Metrics, MetricsAdmin)
admin.site.register(NewsAttachment, NewsAttachmentsAdmin)
admin.site.register(PredictionCount)
#
