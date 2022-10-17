import re
from datetime import timedelta
from collections import defaultdict

from bytewax.dataflow import Dataflow
from bytewax.inputs import ManualInputConfig
from bytewax.outputs import StdOutputConfig, ManualOutputConfig
from bytewax.execution import run_main
from bytewax.window import TumblingWindowConfig, SystemClockConfig
from textblob import TextBlob
import spacy

from twitter import get_rules, delete_all_rules, get_stream, set_stream_rules


en = spacy.load('en_core_web_sm')
sw_spacy = en.Defaults.stop_words

def input_builder(worker_index, worker_count, resume_state):
    return get_stream()


def remove_emoji(tweet):
    """
    This function takes in a tweet and strips off most of the emojis for the different platforms
    :param tweet:
    :return: tweet stripped off emojis
    """
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                               u"\U00002702-\U000027B0"
                               u"\U000024C2-\U0001F251"
                               "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', tweet)


def remove_username(tweet):
    """
    Remove all the @usernames in a tweet
    :param tweet:
    :return: tweet without @username
    """
    return re.sub('@[\w]+', '', tweet)


def clean_tweet(tweet):
    """
    Removes spaces and special characters to a tweet
    :param tweet:
    :return: clean tweet
    """
    return ' '.join(re.sub("(@[A-Za-z0-9]+)|([^0-9A-Za-z \t])|(\w+:\/\/\S+)", " ", tweet).split())


def get_tweet_sentiment(tweet):
    """
    Determines the sentiment of a tweet whether positive, negative or neutral
    :param tweet:
    :return: sentiment and the tweet
    """
    # create TextBlob object
    get_analysis = TextBlob(tweet)
    # get sentiment
    if get_analysis.sentiment.polarity > 0:
        return 'positive', tweet
    elif get_analysis.sentiment.polarity == 0:
        return 'neutral', tweet
    else:
        return 'negative', tweet

def tokenize(sentiment__text):
    key, text = sentiment__text
    tokens = re.findall(r'[^\s!,.?":;0-9]+', text)
    data = [(key, word.lower()) for word in tokens if word.lower() not in sw_spacy]
    return data

# Add a fold window to capture the count of words
# grouped by positive, negative and neutral sentiment
# over 1 minute period and then write them to a file
cc = SystemClockConfig()
wc = TumblingWindowConfig(length=timedelta(seconds=60))

def count_words():
    return defaultdict(lambda:0)


def count(results, word):
    results[word] += 1
    return results


def sort_dict(key__data):
    key, data = key__data
    return (key, sorted(data.items(), key=lambda k_v: k_v[1], reverse=True)[:10])


def output_builder2(worker_index, worker_count):
    def write_to_file(key__data):
        sentiment, data = key__data
        with open(f"outfile_{sentiment}.txt", 'w') as f:
            f.seek(0)
            for key, value in data:
                f.write(f"{key}, {value}\n")
    
    return write_to_file


if __name__ == "__main__":

    rules = get_rules()
    delete = delete_all_rules(rules)

    # get search terms
    with open("search_terms.txt", "+r") as f:
        search_terms = f.read().splitlines()
    
    print(search_terms)
    ## set stream rules
    set_stream_rules(search_terms)

    flow = Dataflow()
    flow.input("input", ManualInputConfig(input_builder))
    flow.map(remove_emoji)
    flow.map(remove_username)
    flow.map(clean_tweet)
    flow.map(get_tweet_sentiment)
    flow.flat_map(tokenize)
    # flow.inspect(print)
    # flow.capture(ManualOutputConfig(output_builder1))
    flow.fold_window(
        "count_words", 
        cc, 
        wc, 
        builder = count_words, 
        folder = count)
    flow.map(sort_dict)
    flow.capture(ManualOutputConfig(output_builder2))

    run_main(flow)
