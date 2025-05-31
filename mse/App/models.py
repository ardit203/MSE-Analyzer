from django.db import models

# Create your models here.

class Issuer(models.Model):
    code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    dashed = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.code} - {self.dashed}'

class TopIssuer(models.Model):
    # code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    issuer = models.OneToOneField(Issuer, related_name='top_issuer', on_delete=models.CASCADE)
    def __str__(self):
        return self.issuer.code

class Stock(models.Model):
    # code = models.CharField(max_length=20, null=True, blank=True)
    issuer = models.ForeignKey(Issuer, related_name='stocks', on_delete=models.CASCADE)
    date = models.DateField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
    min = models.FloatField(null=True, blank=True)
    max = models.FloatField(null=True, blank=True)
    avg = models.FloatField(null=True, blank=True)
    chg = models.FloatField(null=True, blank=True)
    volume = models.IntegerField(null=True, blank=True)
    turnover = models.IntegerField(null=True, blank=True)
    total_turnover = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('issuer', 'date')

    def __str__(self):
        return f'{self.issuer.code} - {self.date} - {self.price}'


class LastDate(models.Model):

    # code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    issuer = models.OneToOneField(Issuer, related_name='last_date', on_delete=models.CASCADE)
    date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['issuer'], name='unique_issuer_last_date')
        ]


class New(models.Model):
    # code = models.CharField(max_length=10, null=True, blank=True)
    issuer = models.ForeignKey(Issuer, related_name='news', on_delete=models.CASCADE)
    title_en = models.CharField(max_length=100, null=True, blank=True)
    title_al = models.CharField(max_length=100, null=True, blank=True)
    title_mk = models.CharField(max_length=100, null=True, blank=True)
    document_id = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateField()
    link = models.CharField(max_length=100, null=True, blank=True)
    api = models.CharField(max_length=100, null=True, blank=True)
    content_en = models.TextField(null=True, blank=True)
    content_al = models.TextField(null=True, blank=True)
    content_mk = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('issuer', 'date', 'document_id')

    def __str__(self):
        return f'{self.issuer.code} - {self.title_en} - {self.date}'


class NewsAttachment(models.Model):
    new = models.ForeignKey(New, related_name='attachments', on_delete=models.CASCADE)
    attachment_id = models.CharField(max_length=100, null=True, blank=True)
    attachment_link = models.CharField(max_length=100, null=True, blank=True)
    file_name_en = models.CharField(max_length=100, null=True, blank=True)
    file_name_al = models.CharField(max_length=100, null=True, blank=True)
    file_name_mk = models.CharField(max_length=100, null=True, blank=True)
    type = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.new.issuer.code} - {self.new.document_id} - {self.attachment_id} - {self.type}'


class Fundamental(models.Model):
    # code = models.CharField(max_length=10, null=True, blank=True, unique=True)
    issuer = models.OneToOneField(Issuer, related_name='fundamental', on_delete=models.CASCADE)
    label = models.CharField(max_length=20)
    score = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['issuer'], name='unique_issuer_fundamental')
        ]

    def __str__(self):
        return f'{self.issuer.code} - {self.label}'


class TechnicalIndicator(models.Model):
    TIMEFRAME_CHOICES = [
        ('1d', '1 Day'),
        ('1w', '1 Week'),
        ('1m', '1 Month'),
        ('14d', '14 Days'),
    ]

    INDICATOR_CHOICES = [
        ('sma', 'Simple Moving Average'),
        ('ema', 'Exponential Moving Average'),
        ('wma', 'Weighted Moving Average'),
        ('hma', 'Hull Moving Average'),
        ('tema', 'Triple Exponential Moving Average'),
        ('rsi', 'Relative Strength Index'),
        ('kvo', 'Klinger Volume Oscillator'),
        ('cci', 'Commodity Channel Index'),
        ('cmo', 'Chande Momentum Oscillator'),
        ('wpr', 'Williams %R')
    ]
    issuer = models.ForeignKey(Issuer, on_delete=models.CASCADE, related_name='technical_indicators')
    # code = models.CharField(max_length=20, null=True, blank=True)
    indicator_type = models.CharField(max_length=30, choices=INDICATOR_CHOICES, null=True, blank=True)
    timeframe = models.CharField(max_length=3, choices=TIMEFRAME_CHOICES, null=True, blank=True)
    date = models.DateField(null=True, blank=True)  # the date this indicator was calculated
    value = models.FloatField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
    signal = models.CharField(max_length=20, null=True, blank=True)
    class Meta:
        unique_together = ('issuer', 'indicator_type', 'timeframe', 'date')

    def __str__(self):
        return f"{self.issuer.code} - {self.indicator_type.upper()} - {self.timeframe} - {self.date} - {self.signal}"


class Prediction(models.Model):
    # code = models.CharField(max_length=20, null=True, blank=True)
    issuer = models.ForeignKey(Issuer, related_name='predictions', on_delete=models.CASCADE)
    date = models.DateField()
    predicted_price = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('issuer', 'date')

    def __str__(self):
        return f'{self.issuer.code} - {self.predicted_price}'

class LastPredictionDate(models.Model):
    issuer = models.OneToOneField(Issuer, related_name='last_prediction_date', on_delete=models.CASCADE)
    date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['issuer'], name='unique_issuer_last_date_prediction')
        ]

class PredictionCount(models.Model):
    count = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f'{self.count}'

class Metrics(models.Model):
    issuer = models.OneToOneField(Issuer, related_name='metrics', on_delete=models.CASCADE)
    # code = models.CharField(max_length=20, null=True, blank=True)
    r2_score = models.FloatField(null=True, blank=True)
    mse = models.FloatField(null=True, blank=True)
    mae = models.FloatField(null=True, blank=True)
    mape = models.FloatField(null=True, blank=True)
    msle = models.FloatField(null=True, blank=True)
    max = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f'{self.issuer.code} - {self.r2_score}'
