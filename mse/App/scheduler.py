import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events
from . import scripts

def fetch_data_job():
    print('...STARTED DATA PROCESSING...')
    start_t = time.time()
    issuers = scripts.ScrapeIssuers()
    stock = scripts.ScrapeStockData()
    news = scripts.NewsScraper()
    translator = scripts.NewsTranslator()
    technical = scripts.TechnicalAnalysis()
    fundamental = scripts.FundamentalAnalysis()
    prediction = scripts.PredictionLSTM()

    issuers.start()
    stock.start()
    translator.start(news.start())
    technical.start()
    fundamental.start()
    prediction.start()
    print('TIME TAKEN TO PROCESS DATA', round((time.time() - start_t) / 60, 2), 'min  or ',
          round(time.time() - start_t, 2), 'sec')

def start():
    scheduler = BackgroundScheduler(timezone="Europe/Skopje")
    scheduler.add_jobstore(DjangoJobStore(), "default")

    scheduler.add_job(
        fetch_data_job,
        trigger=CronTrigger(hour=15, minute=30),
        # trigger=CronTrigger(minute='*/5'),
        id="fetch_data_job",
        max_instances=1,
        replace_existing=True,
    )

    register_events(scheduler)
    scheduler.start()
    print("Scheduler started...")
