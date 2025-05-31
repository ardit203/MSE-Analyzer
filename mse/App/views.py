import json
import os
from datetime import datetime, timedelta, date
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .forms import *
from .models import *


def save_query_params(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        request.session['saved_query_params'] = data
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'Invalid method'}, status=400)

def open_language_file(lang):
    file_path = os.path.join(settings.BASE_DIR, 'App', 'static', 'lang', f'{lang}.json')

    with open(file_path, 'r', encoding='utf-8') as f:
        lang_data = json.load(f)

    return lang_data

def get_params(request, keys=None):
    params = request.GET.dict()

    if not params and 'saved_query_params' in request.session:
        params = request.session.pop('saved_query_params')
    if keys:
        return {k: params.get(k) for k in keys if k in params}
    return params

def home(request, lang):
    lang_data = open_language_file(lang)

    top_issuers = [top_issuer.issuer for top_issuer in TopIssuer.objects.all()]


    rsp = {
        'data': [],
        'stats': {
            'date': None,
            'total': 0,
            'expensive': None,
            'cheap': None,
            'max_chg': None,
            'min_chg': None,
            'winners': 0,
            'losers': 0,
            'neutral': 0,
            'exchange': '1 EUR = 61,51 MKD',
        }
    }

    for issuer in top_issuers:
        data = issuer.stocks.order_by('-date').values().first()

        if not data:
            continue
        data["code"] = issuer.code  # or any key/value you want to add
        rsp['data'].append(data)

        chg = data['chg']
        avg = data['avg']
        turnover = data['turnover']

        # Classify by change
        if chg > 0:
            rsp['stats']['winners'] += 1
        elif chg < 0:
            rsp['stats']['losers'] += 1
        else:
            rsp['stats']['neutral'] += 1

        # Accumulate stats
        rsp['stats']['total'] += turnover
        rsp['stats']['expensive'] = max(rsp['stats']['expensive'], avg) if rsp['stats'][
                                                                               'expensive'] is not None else avg
        rsp['stats']['cheap'] = min(rsp['stats']['cheap'], avg) if rsp['stats']['cheap'] is not None else avg
        rsp['stats']['max_chg'] = max(rsp['stats']['max_chg'], chg) if rsp['stats']['max_chg'] is not None else chg
        rsp['stats']['min_chg'] = min(rsp['stats']['min_chg'], chg) if rsp['stats']['min_chg'] is not None else chg

        # Update date (use the latest one you encounter)
        if not rsp['stats']['date']:
            rsp['stats']['date'] = data['date']

    return render(request, 'home.html', {'lang': lang, 'lang_data': lang_data, 'data': rsp})

def redirect_home(request):
    return redirect('/en/home/')

def get_default_dates():
    end_date = datetime.today().date()
    start_date = end_date - timedelta(days=30)
    return start_date, end_date

def get_issuer_by_code(code):
    return Issuer.objects.filter(code=code).first()

def get_stocks(issuer, start_date, end_date, order):
    return issuer.stocks.filter(date__range=[start_date, end_date]).order_by(order)


def default_issuer_vis_tech(request, lang, order, form_name='DateRangeForm'):
    lang_data = open_language_file(lang)

    # Handle GET params
    params = get_params(request, keys=['issuer', 'start_date', 'end_date'])
    if params:
        issuer = get_issuer_by_code(params.get('issuer'))
        start_date = params.get('start_date')
        end_date = params.get('end_date')

    # Handle POST form
    elif request.method == 'POST':
        if form_name == 'DateRangeForm':
            form = DateRangeForm(request.POST, lang_data=lang_data)
        else:
            form = TechnicalForm(request.POST, lang_data=lang_data)
        if form.is_valid():
            issuer = get_issuer_by_code(form.cleaned_data['issuer'])
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
        else:
            issuer = None
            start_date, end_date = None, None
    else:
            issuer = get_issuer_by_code('ALK')
            start_date, end_date = get_default_dates()

    # Prepare form
    initial_data = {
        'issuer': issuer.code if issuer else '',
        'start_date': start_date,
        'end_date': end_date,
    }

    if form_name == 'DateRangeForm':
        form = DateRangeForm(initial=initial_data, lang_data=lang_data)
    else:
        form = TechnicalForm(initial=initial_data, lang_data=lang_data)


    if issuer and start_date and end_date:
        data = get_stocks(issuer, start_date, end_date, order)
    else:
        data = []


    return {
        'issuer': issuer,
        'start_date': start_date,
        'end_date': end_date,
        'lang_data': lang_data,
        'form': form,
        'data': data,
    }

def issuers_data(request, lang):
    dictionary = default_issuer_vis_tech(request, lang, '-date')

    lang_data = dictionary.get('lang_data')
    stock_data = dictionary.get('data')
    form = dictionary.get('form')

    return render(request, 'issuers-data.html', {
        'lang': lang,
        'lang_data': lang_data,
        'form': form,
        'data': stock_data
    })

def redirect_issuers_data(request):
    return redirect('/en/issuers-data/')

def extract_stock_data_for_visualization(stock_data, fields):
    rsp = {field: [] for field in fields}
    for datum in stock_data:
        for field in fields:
            rsp[field].append(getattr(datum, field))
    return json.dumps(rsp, default=str)

def visualization(request, lang):
    dictionary = default_issuer_vis_tech(request, lang, 'date')
    lang_data = dictionary.get('lang_data')
    stock_data = dictionary.get('data')
    form = dictionary.get('form')

    fields = ['date', 'price', 'max', 'min', 'avg', 'chg', 'volume', 'turnover', 'total_turnover']
    stock_json = extract_stock_data_for_visualization(stock_data, fields)

    return render(request, 'visualization.html', {
        'lang': lang,
        'lang_data': lang_data,
        'form': form,
        'data': stock_json
    })

def redirect_visualization(request):
    return redirect('/en/visualization/')

def build_indicator_summary(indicators, lang_data):
    mas = {'sma', 'ema', 'hma', 'wma', 'tema'}
    ma, osc = [], []

    summary = {
        'ma_count': {'buy': 0, 'sell': 0, 'hold': 0},
        'osc_count': {'buy': 0, 'sell': 0, 'hold': 0},
        'overall': {'buy': 0, 'sell': 0, 'hold': 0},
    }

    for ind in indicators:
        group = ma if ind.indicator_type in mas else osc
        group.append({
            'indicator_type': lang_data['technical']['indicator'][ind.indicator_type],
            'timeframe': lang_data['technical']['timeframe'][ind.timeframe],
            'value': ind.value,
            'signal': ind.signal
        })
        category = 'ma_count' if ind.indicator_type in mas else 'osc_count'
        summary[category][ind.signal] += 1
        summary['overall'][ind.signal] += 1

    return ma, osc, summary

def technical(request, lang):
    dictionary = default_issuer_vis_tech(request, lang, 'date', 'TechnicalForm')
    lang_data = dictionary.get('lang_data')
    stock_data = dictionary.get('data')
    form = dictionary.get('form')
    end_date = dictionary.get('end_date')
    issuer = dictionary.get('issuer')

    fields = ['date', 'price', 'max', 'min', 'avg']
    stock_json = extract_stock_data_for_visualization(stock_data, fields)

    if not isinstance(end_date, date):
        # Parse from string (adjust format if needed)
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    tech = issuer.technical_indicators.filter(date__range=[end_date-timedelta(days=7), end_date])
    valid_date = tech.filter(date__lte=end_date).order_by('-date').values_list('date', flat=True).first()
    last_indicators = tech.filter(date=valid_date)

    ma, osc, summary = build_indicator_summary(last_indicators, lang_data)


    return render(
        request,
        'technical.html',
        {
            'lang': lang,
            'lang_data': lang_data,
            'form': form,
            'stock': stock_json,
            'moving_averages': ma,
            'oscillators': osc,
            'summary': summary
        }
    )

def redirect_technical(request):
    return redirect('/en/technical/')

def fundamental(request, lang):
    lang_data = open_language_file(lang)

    params = get_params(request, keys=['issuer'])

    if params:
        issuer = get_issuer_by_code(params.get('issuer'))

    elif request.method == 'POST':
        form = FundamentalForm(request.POST, lang_data=lang_data)
        if form.is_valid():
            issuer = get_issuer_by_code(form.cleaned_data['issuer'])
        else:
            issuer = None
    else:
        issuer = get_issuer_by_code('ALK')

    # Prepare form
    initial_data = {
        'issuer': issuer.code if issuer else '',

    }
    form = FundamentalForm(initial=initial_data, lang_data=lang_data)

    if issuer:
        data = issuer.news.all()
        sentiment = issuer.fundamental
    else:
        data = []
        sentiment = None


    dicts_list = []
    for datum in data:
        data_dict = {
            'code': datum.issuer.code,
            'title': getattr(datum, f'title_{lang}', ''),
            'date': datum.date,
            'document_id': datum.document_id,
            'content': getattr(datum, f'content_{lang}', ''),
        }
        dicts_list.append(data_dict)

    return render(request, 'fundamental.html', {
        'lang': lang,
        'lang_data': lang_data,
        'form': form,
        'data': dicts_list,
        'sentiment': sentiment
    })

def news(request, lang, document_id, issuer):
    lang_data = open_language_file(lang)

    new = New.objects.filter(document_id=document_id).first()

    new_dict = {
        'code': new.issuer.code,
        'date': new.date,
        'document_id': new.document_id,
        'title': getattr(new, f'title_{lang}', ''),
        'content': getattr(new, f'content_{lang}', ''),
    }




    attachments = new.attachments.all()




    attachments_list = []
    for attachment in attachments:
        file_name = getattr(attachment, f'file_name_{lang}', None) or getattr(attachment, 'file_name_mk', '')
        attachment_dict = {
            'attachment_id': attachment.attachment_id,
            'file_name': file_name,
            'attachment_link': attachment.attachment_link,
            'type': attachment.type
        }
        attachments_list.append(attachment_dict)

    request.session['issuer'] = new.issuer.code
    return render(request, 'news.html', {
        'lang': lang,
        'lang_data': lang_data,
        'new': new_dict,
        'attachments': attachments_list
    })

def redirect_fundamental(request):
    return redirect('/en/fundamental/')

def prediction(request, lang):
    lang_data = open_language_file(lang)

    params = get_params(request, keys=['issuer'])

    if params:
        issuer = get_issuer_by_code(params.get('issuer'))

    elif request.method == 'POST':
        form = PredictionForm(request.POST, lang_data=lang_data)
        if form.is_valid():
            issuer = get_issuer_by_code(form.cleaned_data['issuer'])
        else:
            issuer = None
    else:
        issuer = get_issuer_by_code('ALK')

    # Prepare form
    initial_data = {
        'issuer': issuer.code if issuer else '',

    }
    form = PredictionForm(initial=initial_data, lang_data=lang_data)

    # Fetch data
    if issuer:
        data = issuer.predictions.all()
        metrics = issuer.metrics
        last_stock = Stock.objects.filter(issuer=issuer).order_by('-date')[:20]
    else:
        data = []
        metrics = None
        last_stock = None


    last_price = last_stock[0].price if last_stock else None
#
    rsp = {
        'date': [],
        'price': [],
        'pred_date': [],
        'pred_price': [],
    }



    for datum in last_stock:
        rsp['date'].append(datum.date)
        rsp['price'].append(datum.price)

    for datum in data:
        rsp['pred_date'].append(datum.date)
        rsp['pred_price'].append(datum.predicted_price)

    rsp_json = json.dumps(rsp, default=str)

    return render(request, 'prediction.html', {'lang': lang, 'lang_data': lang_data, 'form':form, 'metrics': metrics, 'data': data, 'last_price': last_price, 'last_stock': last_stock, 'chart_data': rsp_json})

def redirect_prediction(request):
    return redirect('/en/prediction/')
