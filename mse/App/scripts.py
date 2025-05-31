import pandas_ta
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import threading
from queue import Queue
import re
from deep_translator import GoogleTranslator
from threading import Thread, Lock
import logging
from transformers import pipeline
import time
import pandas as pd
from keras import Sequential, Input
from keras.callbacks import EarlyStopping
from keras.layers import LSTM, Dense, Dropout
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, mean_absolute_percentage_error, \
    mean_squared_log_error, max_error
from sklearn.preprocessing import MinMaxScaler
from datetime import timedelta
import joblib
import tensorflow as tf
from keras.models import load_model
import shutil
import os
from .models import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_issuers(content):
    issuers = [
        Issuer(code=code, name=name, dashed=dashed)
        for code, name, dashed in content
    ]
    Issuer.objects.bulk_create(issuers, ignore_conflicts=True)

def create_top_issuers(content, existing_issuers):
    if not existing_issuers:
        existing_issuers = Issuer.objects.all()
    top_issuers = sorted(
        [TopIssuer(issuer=existing_issuers.filter(code=code).first()) for code in content],
        key=lambda x: x.issuer.code
    )

    TopIssuer.objects.bulk_create(top_issuers, ignore_conflicts=True)

class ScrapeIssuers:
    _top_issuers = ['GRNT', 'SLAV', 'REPL', 'ADIN', 'TEL', 'MPT', 'TNB', 'ALK', 'STB', 'KMB', 'UNI']

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=3,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def _fetch_issuers(self, existing_codes):
        url = 'https://www.mse.mk/en/stats/symbolhistory/KMB'
        response = self.session.get(url)

        while response.status_code != 200:
            response = requests.get(url)

        soup = BeautifulSoup(response.content, 'html.parser')

        issuers_dropdown = soup.find('select', {'id': 'Code'})
        issuers = []

        for option in issuers_dropdown.find_all('option'):
            code = option.get('value')

            if code in existing_codes:
                print(f'Already exists --{code}---')
                continue

            if code and any(char.isdigit() for char in code):
                print(f'Contains digits --{code}---')
                continue

            url = f'https://www.mse.mk/IssuerSelection/symbol/{code}'
            response = self.session.get(url)

            while response.status_code != 200:
                response = requests.get(url)

            soup = BeautifulSoup(response.content, 'html.parser')
            name = None
            issuer_div = soup.find('div', class_='col-md-8 title')

            if issuer_div:
                name = issuer_div.get_text(strip=True)
            else:
                title_div = soup.find('div', id='titleKonf2011')
                if title_div:
                    text = title_div.get_text(strip=True)
                    parts = text.split(" - ")
                    if len(parts) >= 3:
                        name = " - ".join(parts[2:]).strip()
                    else:
                        name = None

            if name is None:
                print(f'No name --{code}---')
                continue

            if 'dolgorocno suspendirano od kotacija' in name:
                print(f'Suspended --{code}---')
                continue

            dashed = None
            link_tag = soup.find("a", href=re.compile(r"^/IssuerSelection/rss/seinet/"))

            if link_tag:
                dashed = link_tag['href'].replace("/IssuerSelection/rss/seinet/", "")

            if dashed is None:
                print(f'No dashed ---{code}---',)
                continue

            issuers.append([code, name, dashed])
        create_issuers(issuers)
        return issuers

    def start(self):
        print("STARTED SCRAPING ISSUERS")
        start_t = time.time()
        existing_issuers = Issuer.objects.all()
        existing_codes = set(existing_issuers.values_list('code', flat=True))
        self._fetch_issuers(existing_codes)
        create_top_issuers(self._top_issuers, existing_issuers)
        print('TIME TAKEN TO SCRAPE ISSUERS: ', round((time.time() - start_t) / 60, 2), 'min  or ',
              round(time.time() - start_t, 2), 'sec')

class ScrapeStockData:
    _stocks = []
    _top_issuers = ('GRNT', 'SLAV', 'REPL', 'ADIN', 'TEL', 'MPT', 'TNB', 'ALK', 'STB', 'KMB', 'UNI')
    _last_dates = []

    def __init__(self):
        self._lock = Lock()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=3,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def _parse_cells(self, row):
        translation_table = str.maketrans({',': ''})
        cells = row.find_all('td')

        if len(cells) < 9:
            return None

        def safe_float(cell, default):
            try:
                return float(cell.text.translate(translation_table)) if cell and cell.text.strip() else default
            except (AttributeError, ValueError):
                return None

        def safe_int(cell, default):
            try:
                return int(cell.text.translate(translation_table)) if cell and cell.text.strip() else default
            except (AttributeError, ValueError):
                return None

        def safe_date(cell):
            try:
                raw = cell.text.strip()
                parsed = datetime.strptime(raw, '%m/%d/%Y')
                return parsed.date()
            except (AttributeError, ValueError):
                return None

        if not cells[1].text.strip():
            return None


        date = safe_date(cells[0])
        last_trade_price = safe_float(cells[1], None)
        max = safe_float(cells[2], last_trade_price)
        min = safe_float(cells[3], last_trade_price)
        avg_price = safe_float(cells[4], None)
        chg = safe_float(cells[5], None)
        volume = safe_int(cells[6], 0)
        turnover_in_best = safe_int(cells[7], 0)
        total_turnover = safe_int(cells[8], 0)

        result = [date, last_trade_price, max, min, avg_price, chg, volume, turnover_in_best, total_turnover]
        return result

    def _parse_soup(self, bs):
        table = bs.find_all('tbody')

        if len(table) == 0:
            return None

        table = table[0]
        rows = table.find_all('tr')
        res = []
        for row in rows:
            parsed = self._parse_cells(row)
            if parsed is None:
                continue
            res.append(parsed)

        if not res:
            return None
        return res

    def _request_HTTP(self, code, start_date, end_date):
        start_date_str = start_date.strftime('%m/%d/%Y')
        end_date_str = end_date.strftime('%m/%d/%Y')
        base_url = 'https://www.mse.mk/en/stats/symbolhistory/'
        url = base_url + code + "?" + "FromDate=" + start_date_str + '&ToDate=' + end_date_str

        retries = 5
        for _ in range(retries):
            try:
                response = self.session.post(url, timeout=(25, 60))
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                res = self._parse_soup(soup)
                return res
            except requests.exceptions.RequestException as e:
                print(f"Error: {e}. Retrying...")
                time.sleep(1)
        print(f"Failed to fetch data for {code} after {retries} attempts.")
        return None

    def _fetch_range(self, issuer, start_date, end_date):
        stock_data = []
        while end_date > start_date:
            fetch_start = max(start_date, end_date - timedelta(days=365))
            parsed = self._request_HTTP(issuer.code, fetch_start, end_date)

            if parsed:
                stock_data += parsed

            end_date = fetch_start - timedelta(days=1)

        if stock_data:
            with self._lock:
                self._last_dates.append(LastDate(issuer=issuer, date=stock_data[0][0]))
                for row in stock_data:
                    self._stocks.append(
                        Stock(
                            issuer=issuer,
                            date=row[0],
                            price=row[1],
                            max=row[2],
                            min=row[3],
                            avg=row[4],
                            chg=row[5],
                            volume=row[6],
                            turnover=row[7],
                            total_turnover=row[8]
                        )
                    )
                print(f"Finished ---{issuer.code}---")

    def _fetch_data(self, issuers):
        threads = []
        today = (datetime.today()).date()
        last_dates = {}
        all_last_dates = LastDate.objects.all()
        prediction_dates = all_last_dates.filter(issuer__code__in=self._top_issuers)

        if prediction_dates:
            pred_dates = []
            for date in prediction_dates:
                pred_dates.append(
                    LastPredictionDate(
                        issuer=date.issuer,
                        date=date.date
                    )
                )
            LastPredictionDate.objects.bulk_create(
                pred_dates,
                update_conflicts=True,
                update_fields=['date'],
                unique_fields=['issuer']
            )

        for ld in all_last_dates:
            key = ld.issuer.code
            last_dates[key] = ld

        for issuer in issuers:
            last_date = last_dates.get(issuer.code)
            if last_date:
                search_from = last_date.date
            else:
                search_from = today - timedelta(days=365 * 30)

            thread = Thread(target=self._fetch_range, args=(issuer, search_from, today))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        Stock.objects.bulk_create(self._stocks, ignore_conflicts=True)
        LastDate.objects.bulk_create(
            self._last_dates,
            update_conflicts=True,
            update_fields=['date'],
            unique_fields=['issuer']
        )

    def start(self):
        print("STARTED SCRAPING STOCK DATA")
        start_t = time.time()
        issuers = Issuer.objects.all()
        self._fetch_data(issuers)
        print('TIME TAKEN TO SCRAPE STOCK DATA: ', round((time.time() - start_t) / 60, 2), 'min  or ',
              round(time.time() - start_t, 2), 'sec')

class TechnicalAnalysis:
    _technical_data = []
    _timeframes = {
        '1d': 1,
        '1w': 5,
        '1m': 20,
        '14d': 10,
    }
    _moving_averages = ('sma', 'ema', 'wma', 'hma', 'tema')
    _indicator_map = {
        'sma': '_sma',
        'ema': '_ema',
        'wma': '_wma',
        'hma': '_hma',
        'tema': '_tema',
        'rsi': '_rsi',
        'kvo': '_kvo',
        'cmo':'_cmo',
        'cci': '_cci',
        'wpr': '_wpr'
    }

    def _assemble(self, technical_data, dates, issuer, timeframe, tech_type, prices, signals):
        for value, date, price, signal in zip(technical_data, dates, prices, signals):
            self._technical_data.append(
                TechnicalIndicator(
                    issuer=issuer,
                    indicator_type=tech_type,
                    timeframe=timeframe,
                    date=date,
                    value=value,
                    price=price,
                    signal=signal
                )
            )

    def _generate_signal(self, indicator_values, price_values, tech_type):
        signal = []

        for value, price in zip(indicator_values, price_values):
            if tech_type in self._moving_averages:
                if price > value:
                    signal.append('buy')
                elif value > price:
                    signal.append('sell')
                else:
                    signal.append('hold')
            elif tech_type == 'rsi':
                if value < 30:
                    signal.append('buy')
                elif value > 70:
                    signal.append('sell')
                else:
                    signal.append('hold')
            elif tech_type == 'cci':
                if value < -100:
                    signal.append('buy')
                elif value > 100:
                    signal.append('sell')
                else:
                    signal.append('hold')
            elif tech_type == 'cmo':
                if value < -50:
                    signal.append('buy')
                elif value > 50:
                    signal.append('sell')
                else:
                    signal.append('hold')
            elif tech_type == 'wpr':
                if value < -80:
                    signal.append('buy')
                elif value > -20:
                    signal.append('sell')
                else:
                    signal.append('hold')
            else:
                signal.append('hold')

        return signal

    def _calculate_and_store(self, func, issuer, data, tech_type):
        dates = data['date']
        for label, period in self._timeframes.items():
            if label == '14d':
                continue
            result = func(data['price'], period)
            signals = self._generate_signal(result, data['price'], tech_type)
            self._assemble(result, dates, issuer, label, tech_type, data['price'], signals)

    def _sma(self, issuer, data):
        self._calculate_and_store(lambda price, period: price.rolling(window=period).mean(), issuer, data, 'sma')

    def _ema(self, issuer, data):
        self._calculate_and_store(lambda price, period: price.ewm(span=period, adjust=False).mean(), issuer, data,
                                  'ema')

    def _wma(self, issuer, data):
        self._calculate_and_store(lambda price, period: pandas_ta.wma(price, length=period), issuer, data, 'wma')

    def _hma(self, issuer, data):
        self._calculate_and_store(lambda price, period: pandas_ta.hma(price, length=period), issuer, data, 'hma')

    def _tema(self, issuer, data):
        self._calculate_and_store(lambda price, period: pandas_ta.tema(price, length=period), issuer, data, 'tema')

    def _indicator_14d(self, func, issuer, data, tech_type, uses_high_low=False):
        dates = data['date']
        period = self._timeframes['14d']

        if uses_high_low:
            result = func(high=data['max'], low=data['min'], close=data['price'], length=period)
        else:
            result = func(close=data['price'], length=period)
        signals = self._generate_signal(result, data['price'], tech_type)
        self._assemble(result, dates, issuer, '14d', tech_type, data['price'], signals)

    def _rsi(self, issuer, data):
        self._indicator_14d(pandas_ta.rsi, issuer, data, 'rsi')

    def _cci(self, issuer, data):
        self._indicator_14d(pandas_ta.cci, issuer, data, 'cci', uses_high_low=True)

    def _cmo(self, issuer, data):
        self._indicator_14d(pandas_ta.cmo, issuer, data, 'cmo', uses_high_low=True)

    def _wpr(self, issuer, data):
        self._indicator_14d(pandas_ta.willr, issuer, data, 'wpr', uses_high_low=True)

    def _kvo(self, issuer, data):
        dates = data['date']
        kvo = pandas_ta.kvo(high=data['max'], low=data['min'], close=data['price'], volume=data['volume'], signal=10)
        signals = []

        for i in range(1, len(kvo)):
            if pd.isna(kvo.loc[i, 'KVO_34_55_10']) or pd.isna(kvo.loc[i, 'KVOs_34_55_10']):
                signals.append('hold')
                continue
            prev_kvo = kvo.loc[i - 1, 'KVO_34_55_10']
            prev_signal = kvo.loc[i - 1, 'KVOs_34_55_10']
            curr_kvo = kvo.loc[i, 'KVO_34_55_10']
            curr_signal = kvo.loc[i, 'KVOs_34_55_10']

            if (curr_kvo > curr_signal) and (prev_kvo <= prev_signal):
                signals.append('buy')
            elif (curr_kvo < curr_signal) and (prev_kvo >= prev_signal):
                signals.append('sell')
            else:
                signals.append('hold')

        signals.insert(0, 'hold')
        self._assemble(kvo['KVO_34_55_10'], dates, issuer, '14d', 'kvo', data['price'], signals)

    def _technical_implementation(self, issuers):
        for issuer in issuers:
            if issuer.dashed is None:
                continue

            print(f"\nChecking indicators for issuer: {issuer}")
            for indicator in self._indicator_map:
                queryset = issuer.stocks.order_by('date')
                if not queryset:
                    continue
                data = pd.DataFrame.from_records(queryset.values())
                method_name = self._indicator_map.get(indicator)
                method = getattr(self, method_name, None)

                if method:
                    method(issuer, data)
                else:
                    print(f"⚠️ No method found for indicator: {indicator}")
            print(f"Finished with: {issuer}")
        TechnicalIndicator.objects.bulk_create(self._technical_data, ignore_conflicts=True)

    def start(self):
        print("STARTED TECHNICAL ANALYSIS")
        start_t = time.time()
        TechnicalIndicator.objects.all().delete()
        issuers = [top_issuer.issuer for top_issuer in TopIssuer.objects.all()]
        self._technical_implementation(issuers)
        print('TIME TAKEN FOR TECHNICAL ANALYSIS: ', round((time.time() - start_t) / 60, 2), 'min  or ',
              round(time.time() - start_t, 2), 'sec')

class NewsScraper:
    _file_types = {
        'application/pdf': 'pdf',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.ms-excel': 'xlsx',
        'application/msword': 'doc',

    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=3,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.news_queue = Queue()
        self.lock = threading.Lock()

    def _process_issuer(self, issuer):
        if issuer.dashed is None:
            return

        try:
            rss_url = f"https://www.mse.mk/mk/rss/seinet/{issuer.dashed}"
            response = self.session.get(rss_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml-xml')
            items = soup.find_all('item')

            issuer_news = {
                'issuer': issuer,
                'data': []
            }
            for item in items:
                try:
                    news_content = self._extract_news_content(item)
                    if news_content:
                        issuer_news['data'].append(news_content)
                except Exception as e:
                    logger.error(f"Error processing news item for {issuer.code}: {str(e)}")
                    continue

            if issuer_news['data']:
                with self.lock:
                    print(f"{issuer.code}: {len(issuer_news['data'])} items processed")
                self.news_queue.put(issuer_news)
        except Exception as e:
            logger.error(f"Error processing issuer {issuer.code}: {str(e)}")

    def _scrape_news(self, issuers):
        all_news = {}
        threads = []
        max_threads = 10

        for issuer in issuers:
            thread = threading.Thread(target=self._process_issuer, args=(issuer,))
            thread.start()
            threads.append(thread)

            while len([t for t in threads if t.is_alive()]) >= max_threads:
                time.sleep(0.1)

        for thread in threads:
            thread.join()

        while not self.news_queue.empty():
            result = self.news_queue.get()
            all_news[result['issuer'].code] = result

        return all_news

    def _extract_news_content(self, item):
        try:
            link = item.find('link').text
            document_id = link.split('/')[-1]
            title_mk = item.find('title').text.split(' - ')[2]
            date = datetime.strptime(item.find('pubDate').text, '%a, %d %b %Y %H:%M:%S %z').date()

            api_url = f"https://api.seinet.com.mk/public/documents/single/{document_id}"
            response = self.session.get(api_url)
            response.raise_for_status()
            content_data = response.json()
            data = content_data.get('data')
            attachments = data.get('attachments', [])

            return {
                'document_id': document_id,
                'title_mk': title_mk,
                'date': date,
                'link': link,
                'api': api_url,
                'content_mk': BeautifulSoup(data.get('content', ''), 'html.parser').get_text(separator=' ', strip=True),
                'attachments': self._process_attachments(attachments)
            }
        except Exception as e:
            logger.error(f"Error extracting news content: {str(e)}")
            return None

    def _process_attachments(self, attachments):
        processed_attachments = []
        for attachment in attachments:
            try:
                file_name_mk = attachment.get('fileName', '')
                attachment_id = attachment.get('attachmentId')
                attachment_link = f'https://api.seinet.com.mk/public/documents/attachment/{attachment_id}'
                attachment_type = attachment.get('attachmentType').get('mimeType')
                attachment_description = attachment.get('attachmentType').get('description')
                processed_attachments.append({
                    'attachment_id': attachment_id,
                    'attachment_link': attachment_link,
                    'file_name_mk': file_name_mk,
                    'type': self._file_types.get(attachment_type, attachment_type),
                    'description': attachment_description
                })
            except Exception as e:
                logger.error(f"Error processing attachment: {str(e)}")
                continue

        return processed_attachments

    def start(self):
        try:
            print("STARTED SCRAPING NEWS")
            start_t = time.time()
            issuers = [top_issuer.issuer for top_issuer in TopIssuer.objects.all()]
            all_news = self._scrape_news(issuers)
            print('TIME TAKEN TO SCRAPE NEWS: ', round((time.time() - start_t) / 60, 2), 'min  or ',
                  round(time.time() - start_t, 2), 'sec')

            return all_news
        except Exception as e:
            logger.error(f"Error in main execution: {str(e)}")
            return None

def is_fully_cyrillic(filename):
    name_only = os.path.splitext(filename)[0]
    letters = re.findall(r'[A-Za-zА-Яа-яЀ-ӿ]', name_only)
    for char in letters:
        if re.match(r'[A-Za-z]', char):
            return False
    return True

class NewsTranslator:
    _default_title = {
        'Други ценовно чувствителни информации': {
            'al': 'Informacion tjetër i ndjeshëm ndaj çmimit',
            'en': 'Other price sensitive information'
        },
        'Неревидиран биланс на успех 01.01.': {
            'al': 'Pasqyra e të Ardhurave e Pavarur 01.01.',
            'en': 'Unaudited income statement 01.01.'
        },
        'Предлог': {
            'al': 'Propozim',
            'en': 'Proposal'
        },
        'Прашалници за ККУ': {
            'al': 'Pyetësorë për KK',
            'en': 'Questionnaires for KK'
        },
        'Јавен повик за собрание': {
            'al': 'Thirrje publike për asamble',
            'en': 'Public Call for Assembly'
        }
    }
    _news = []
    _attachments = {}
    _news_lock = Lock()

    def _check_and_remove_duplicates(self, news_dict, news_db):
        for new in news_db:
            data = news_dict.get(new.issuer.code).get('data')
            for datum in data[:]:
                if new.document_id == datum.get('document_id'):
                    data.remove(datum)
        return news_dict

    def _translate_single_news(self, issuer, datum):
        mk_to_en = GoogleTranslator(source='mk', target='en')
        mk_to_sq = GoogleTranslator(source='mk', target='sq')
        has_content = True
        has_files = True
        title_mk = datum.get('title_mk')
        content_mk = datum.get('content_mk')

        if not content_mk:
            has_content = False
        attachments_list = datum.get('attachments')

        if not attachments_list:
            has_files = False

        if not has_content and not has_files:
            return

        if title_mk in self._default_title:
            title_en = self._default_title[title_mk]['en']
            title_al = self._default_title[title_mk]['al']
        else:
            try:
                title_en = mk_to_en.translate(title_mk)
                title_al = mk_to_sq.translate(title_mk)
            except Exception as e:
                print(f"Error translating title: {e}")
                title_en = title_mk
                title_al = title_mk

        content_en = ''
        content_al = ''
        if has_content:
            try:
                content_en = mk_to_en.translate(content_mk)
                content_al = mk_to_sq.translate(content_mk)
            except Exception as e:
                print(f"Error translating content: {e}")
                content_en = content_mk
                content_al = content_mk

        if has_files:
            for attachment in attachments_list:
                name = attachment['file_name_mk']
                if is_fully_cyrillic(name):
                    try:
                        file_en = mk_to_en.translate(name)
                        file_al = mk_to_sq.translate(name)
                        attachment['file_name_en'] = file_en
                        attachment['file_name_al'] = file_al
                    except Exception as e:
                        print(f"Error translating file name: {e}")
                        attachment['file_name_en'] = name
                        attachment['file_name_al'] = name
                else:
                    attachment['file_name_en'] = ''
                    attachment['file_name_al'] = ''

        new_news = New(
            issuer=issuer,
            title_en=title_en,
            title_mk=title_mk,
            title_al=title_al,
            content_en=content_en,
            content_mk=content_mk,
            content_al=content_al,
            document_id=datum.get('document_id'),
            date=datum.get('date'),
            link=datum.get('link'),
            api=datum.get('api')
        )

        with self._news_lock:
            self._news.append(new_news)
            self._attachments[datum.get('document_id')] = attachments_list

    def _translate_and_assemble(self, issuer, data):
        threads = []
        max_threads = 10
        active_threads = []

        for datum in data:
            while len(active_threads) >= max_threads:
                active_threads = [t for t in active_threads if t.is_alive()]
                if len(active_threads) >= max_threads:
                    time.sleep(0.1)
            thread = Thread(target=self._translate_single_news, args=(issuer, datum))
            thread.start()
            active_threads.append(thread)
            threads.append(thread)

        for thread in threads:
            thread.join()

    def _assemble_attachments(self):
        saved_news_qs = New.objects.filter(document_id__in=self._attachments.keys())
        saved_news_dict = {n.document_id: n for n in saved_news_qs}
        attachments = []

        for doc_id, new_obj in saved_news_dict.items():
            attachments_ = self._attachments[doc_id]
            if attachments_ is None:
                continue
            for attachment in attachments_:
                news_attachment = NewsAttachment(
                    new=new_obj,
                    attachment_id=attachment.get('attachment_id', ''),
                    attachment_link=attachment.get('attachment_link', ''),
                    file_name_en=attachment.get('file_name_en'),
                    file_name_al=attachment.get('file_name_al'),
                    file_name_mk=attachment.get('file_name_mk'),
                    type=attachment.get('type', ''),
                )
                attachments.append(news_attachment)
        return attachments

    def _implementation(self, news_dict, news_db):
        news_dict = self._check_and_remove_duplicates(news_dict, news_db)

        for key in news_dict.keys():
            issuer = news_dict.get(key).get('issuer')
            data = news_dict.get(key).get('data')
            if key == 'KMB' or key == 'ALK' or key == 'ADIN' or key == 'MPT' or key == 'STB':
                self._translate_and_assemble(issuer, data)

        if self._news:
            New.objects.bulk_create(self._news, ignore_conflicts=True)

        attachments = self._assemble_attachments()
        if self._attachments:
            NewsAttachment.objects.bulk_create(attachments)

    def start(self, news_dict):
        print("STARTED TRANSLATING")
        start_t = time.time()
        news_db = New.objects.all()
        self._implementation(news_dict, news_db)
        print('TIME TAKEN TO TRANSLATE: ', round((time.time() - start_t) / 60, 2), 'min  or ',
              round(time.time() - start_t, 2), 'sec')

def create_fundamental(data):
    fundamentals = []
    for datum in data:
        content = data.get(datum)
        fundamentals.append(
            Fundamental(
                issuer=content.get('issuer'),
                label=content.get('label'),
                score=content.get('score')
            )
        )

    Fundamental.objects.bulk_create(
        fundamentals,
        update_conflicts=True,
        update_fields=['label', 'score'],
        unique_fields=['issuer']
    )

class FundamentalAnalysis:
    _classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

    def _analysis(self, text_list):
            if not text_list:
                return {
                    'label': 'NEUTRAL-NO-NEWS',
                    'score': 0.5
                }
            scores = []
            for txt in text_list:
                chunk = txt[:512].lower()
                try:
                    result = self._classifier(chunk)
                    scores.append(result[0]['score'])
                except Exception as e:
                    logging.error(f"Error running sentiment pipeline: {e}")
            if not scores:
                return {
                    'label': 'NEUTRAL-NO-NEWS',
                    'score': 0.5
                }
            avg_score = round((sum(scores) / len(scores)),2)
            sentiment = 'NEUTRAL'
            if avg_score > 0.6:
                sentiment = 'POSITIVE'
            elif avg_score < 0.4:
                sentiment = 'NEGATIVE'
            return {
                    'label': sentiment,
                    'score': avg_score
                }

    def _combine(self, issuer):
        new = issuer.news.all()
        if not new:
            return []
        texts = []
        for content in new:
            text = content.content_en
            if text:
                texts.append(text)
        return texts

    def _fundamental_implementation(self, issuers):
        data = {}
        for issuer in issuers:
            texts = self._combine(issuer)
            analysis = self._analysis(texts)
            analysis['issuer'] = issuer
            data[f'{issuer.code}'] = analysis
        create_fundamental(data)

    def start(self):
        print("STARTED FUNDAMENTAL ANALYSIS")
        start_t = time.time()
        issuers = [top_issuer.issuer for top_issuer in TopIssuer.objects.all()]
        self._fundamental_implementation(issuers)
        print('TIME TAKEN FOR FUNDAMENTAL ANALYSIS: ', round((time.time() - start_t) / 60, 2), 'min  or ',
              round(time.time() - start_t, 2), 'sec')

class PredictionLSTM:
    _lag = 30
    _lookback = 10
    _reset = 10
    _prediction_data = []
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    _model_dir = os.path.join(_BASE_DIR, 'App', 'models_dir')
    _scaler_dir = os.path.join(_BASE_DIR, 'App', 'scaler_dir')

    def __init__(self):
        os.makedirs(self._model_dir, exist_ok=True)
        os.makedirs(self._scaler_dir, exist_ok=True)

        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)

    def _get_model_path(self, issuer_code):
        return os.path.join(self._model_dir, f'{issuer_code}_model.h5')

    def _get_scaler_path(self, issuer_code):
        return os.path.join(self._scaler_dir, f'{issuer_code}_scalers.pkl')

    def reset_model_directory(self):
        if os.path.exists(self._model_dir):
            shutil.rmtree(self._model_dir)
        os.makedirs(self._model_dir, exist_ok=True)

    def reset_scaler_directory(self):
        if os.path.exists(self._scaler_dir):
            shutil.rmtree(self._scaler_dir)
        os.makedirs(self._scaler_dir, exist_ok=True)

    def maybe_reset(self):
        count = PredictionCount.objects.first()
        reset = False

        if count:
            print(f'---{count.count}---')

            if count.count == self._reset:
                print("Resetting model and scaler folders...")
                LastPredictionDate.objects.all().delete()
                self.reset_model_directory()
                self.reset_scaler_directory()
                count.count = 0
                reset = True
            else:
                count.count += 1
            count.save()
        else:
            PredictionCount.objects.create(count=0)
            reset=True

        return reset

    def _pre_process(self, issuer, target_date=None):
        if target_date:
            days_needed = self._lag
            untrained_days = issuer.stocks.filter(date__gt=target_date).order_by('date')
            trained_days = issuer.stocks.filter(date__lte=target_date).order_by('-date')[:days_needed+self._lookback]
            trained_days = list(trained_days)[::-1]
            untrained_days = list(untrained_days)
            combined_days = trained_days + untrained_days
            data = [{
                'date': stock.date,
                'price': stock.price,

            } for stock in combined_days]

            df = pd.DataFrame(data)

            for period in range(self._lag, 0, -1):
                df[f'price_{period}'] = df['price'].shift(period)

            df.dropna(inplace=True)
            df.set_index('date', inplace=True)
            return df
        else:
            queryset = issuer.stocks.order_by('date')
            data = pd.DataFrame.from_records(queryset.values())

            if data.empty or 'price' not in data:
                return pd.DataFrame()

            df = data[['date', 'price']].copy()

            for period in range(self._lag, 0, -1):
                df[f'price_{period}'] = df['price'].shift(period)

            df.set_index('date', inplace=True)
            df.dropna(inplace=True)
            return df

    def _LSTM_MODEL(self, data, issuer_code):
        X, Y = data.drop(columns=['price']), data['price']
        model_path = self._get_model_path(issuer_code)
        scaler_path = self._get_scaler_path(issuer_code)

        if os.path.exists(model_path) and os.path.exists(scaler_path):
            model = load_model(model_path)
            scalers = joblib.load(scaler_path)
            scaler_X, scaler_Y = scalers['X'], scalers['Y']
            recent_data = data
            train_X = scaler_X.transform(recent_data.drop(columns=['price']))
            train_Y = scaler_Y.transform(recent_data['price'].to_numpy().reshape(-1, 1))
            train_X = train_X.reshape(train_X.shape[0], self._lag, (train_X.shape[1] // self._lag))
            early_stopping = EarlyStopping(monitor='loss', patience=5, restore_best_weights=True)
            model.fit(train_X, train_Y, epochs=30, batch_size=32, callbacks=[early_stopping])

            return {
                'model': model,
                'scaler_X': scaler_X,
                'scaler_Y': scaler_Y,
            }
        else:
            train_X, test_X, train_Y, test_Y = train_test_split(X, Y, test_size=0.2, shuffle=False)
            scaler_X = MinMaxScaler()
            train_X = scaler_X.fit_transform(train_X)
            test_X = scaler_X.transform(test_X)
            scaler_Y = MinMaxScaler()
            train_Y = scaler_Y.fit_transform(train_Y.to_numpy().reshape(-1, 1))
            train_X = train_X.reshape(train_X.shape[0], self._lag, (train_X.shape[1] // self._lag))
            test_X = test_X.reshape(test_X.shape[0], self._lag, (test_X.shape[1] // self._lag))

            model = Sequential([
                Input((train_X.shape[1], train_X.shape[2],)),
                LSTM(128, return_sequences=True),
                Dropout(0.2),
                LSTM(64),
                Dropout(0.2),
                Dense(1)
            ])
            model.summary()
            model.compile(
                loss="mean_squared_error",
                optimizer="adam",
                metrics=["mean_squared_error"],
            )
            early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
            model.fit(train_X, train_Y, validation_split=0.1, epochs=30, batch_size=32,
                     shuffle=False, callbacks=[early_stopping])
            model.save(model_path)
            joblib.dump({'X': scaler_X, 'Y': scaler_Y}, scaler_path)
            pred_Y = model.predict(test_X)
            pred_Y = scaler_Y.inverse_transform(pred_Y)
            metrics = {
                'r2_score': round(r2_score(test_Y, pred_Y), 2),
                'mse': round(mean_squared_error(test_Y, pred_Y), 2),
                'mae': round(mean_absolute_error(test_Y, pred_Y), 2),
                'mape': round(mean_absolute_percentage_error(test_Y, pred_Y), 2),
                'msle': round(mean_squared_log_error(test_Y, pred_Y), 2),
                'max': round(max_error(test_Y, pred_Y))
            }

            return {
                'model': model,
                'scaler_X': scaler_X,
                'scaler_Y': scaler_Y,
                'metrics': metrics
            }

    def _LSTM_recursive_prediction(self, model, df, scaler_X, scaler_Y, n_days=7, lookback=10):
        df_future = df.copy()
        future_predictions = pd.DataFrame(columns=['date', 'price'])
        last_date = df_future.index[-1]
        next_dates = self._get_next_weekdays(last_date, 7)

        for _ in range(n_days):
            last_window = df_future.iloc[-lookback:].copy()
            scaled = scaler_X.transform(last_window.drop(columns=['price']))
            scaled = scaled.reshape(scaled.shape[0], self._lag, (scaled.shape[1] // self._lag))
            pred_scaled = model.predict(scaled)
            pred_price = scaler_Y.inverse_transform(pred_scaled)[0][0]
            last_columns = [col for col in df_future.columns if col.startswith('price_') and col != f'price_{self._lag}']
            last_values = [df_future[col].iloc[-1] for col in last_columns]
            last_trade_price = df_future['price'].iloc[-1]
            new_row = [round(pred_price, 2)] + last_values + [last_trade_price]
            next_date = next_dates.pop(0)
            df_future.loc[next_date] = new_row
            future_predictions.loc[len(future_predictions)] = [next_date, round(pred_price, 2)]
        return future_predictions

    def _get_next_weekdays(self, start_date, count):
        weekdays = []
        current_date = start_date + timedelta(days=1)

        while len(weekdays) < count:
            if current_date.weekday() < 5:
                weekdays.append(current_date)
            current_date += timedelta(days=1)

        return weekdays

    def _assemble(self, issuer, data):
        for index, row in data.iterrows():
            date = row['date']
            price = row['price']
            self._prediction_data.append(
                Prediction(
                    issuer=issuer,
                    date=date,
                    predicted_price=price
                )
            )

    def _prediction_implementation(self, issuers):
        reset = self.maybe_reset()
        for issuer in issuers:
            print(f'+++{issuer.code}+++')
            last_date = None
            if not reset:
                try:
                    last_date = issuer.last_prediction_date.date
                except LastPredictionDate.DoesNotExist:
                    last_date = None

            data = self._pre_process(issuer, last_date)
            model_data = self._LSTM_MODEL(data, issuer.code)
            df = data.iloc[-self._lookback - 1:].copy()

            future_prices = self._LSTM_recursive_prediction(
                model_data['model'],
                df,
                model_data['scaler_X'],
                model_data['scaler_Y']
            )

            self._assemble(issuer, future_prices)

            if 'metrics' in model_data:
                Metrics.objects.update_or_create(
                    issuer=issuer,
                    defaults=model_data['metrics']
                )

        Prediction.objects.bulk_create(self._prediction_data, ignore_conflicts=True)

    def start(self):
        print("STARTED TRAINING THE MODELS")
        start_t = time.time()
        Prediction.objects.all().delete()
        issuers = [top_issuer.issuer for top_issuer in TopIssuer.objects.all()]
        self._prediction_implementation(issuers)
        print('TIME TAKEN TO TRAIN AND PREDICT: ', round((time.time() - start_t) / 60, 2), 'min  or ',
              round(time.time() - start_t, 2), 'sec')



















