# -*- coding: utf-8 -*-
"""class_final.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/github/ChaitaliV/Splurge/blob/main/location_extractor/class_final.ipynb
"""

from google.colab import drive
drive.mount('/content/drive')

import torch
import torch.nn as nn
import numpy as np
import os
import openai
import re
from transformers import BertTokenizer, BertForTokenClassification
from keras_preprocessing.sequence import pad_sequences
from sklearn.model_selection import train_test_split
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler, TensorDataset
from transformers import AdamW, get_linear_schedule_with_warmup
from tqdm import tqdm, trange
from transformers import BertModel, BertConfig
import requests
import pandas as pd
import inflect
import requests
from bs4 import BeautifulSoup

tokenizer = BertTokenizer.from_pretrained('bert-base-cased')
checkpoint = torch.load('/content/drive/MyDrive/BERT_text_dict.pth',map_location=torch.device('cpu'))
configuration = BertConfig()
model = BertModel(configuration)
model = BertForTokenClassification.from_pretrained("bert-base-cased",num_labels=1882,
    output_attentions = False,
    output_hidden_states = False)
model.load_state_dict({k.replace('module.', ''): v for k, v in checkpoint.items()})
model.to(torch.device('cpu'))
device = 'cpu'
base_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
api_key = "AIzaSyCU7kaDfhZIM4bbJVujlGlhdXphUPke1yY"
engine = "text-davinci-002"
MAX_LEN = 512

class LocationExtractor:
    def __init__(self, sent, city):
        self.device = device
        self.tokenizer = tokenizer
        self.model = model
        self.model.to(self.device)
        self.city = city
        self.sent = sent
        self.categories = ['Restaurant', 'Cafe', 'House', 'Barbecue', 'Bar', 'Pub', 'Palace', 'Kitchen', 'Club', 'Bakery', 'Shop', 'Room', 'Shack', 'Garden', 'Factory', 'Queen', 'Street','Castle', 'Mall', 'Park', 'Palace', 'Temple', 'Masjid', 'Dargah', 'Avenue', 'Gallery', 'Museum', 'Garden', 'Hotel', 'Lake', 'Fort', 'Beach', 'Mandir', 'Hill', 'Bhavan', 'Nation', 'World', 'Center','Pavilion', 'Bistro']

    def clean_string(self, lst, sent):
        l = []
        for ele in lst:
            if ele == ' ' or ele == '':
                pass
            else:
                l.append(ele)
        return l

    def add_suffix(self, p, sent):
        match = re.search(p, sent)
        if match:
            for category in self.categories:
                if match.end() < len(sent) and sent[match.end():].lower().startswith(category.lower()):
                    l = match.group() + '' + category
                    return l
                    break
            return match.group()
        else:
            return p
        
    def add_next_word(self, p, sent):
        match = re.search(p, sent)
        if match:
            s = sent[match.end():].split(' ')
            try: 
              if (s[0] == ''):
                p = p + ' ' + s[1]
              elif (s[0] == ' '):
                p = p + ' ' + s[1]
              else:
                p = p+' '+s[0]
            except:

              pass
        return p

    def extract_location(self, sent):
        true_label = []
        tokenized_sentence = self.tokenizer.encode(sent)
        input_ids = torch.tensor([tokenized_sentence]).to(self.device)
        with torch.no_grad():
            output = self.model(input_ids)
        label_indices = np.argmax(output[0].to('cpu').numpy(), axis=2)
        tokens = self.tokenizer.convert_ids_to_tokens(input_ids.to('cpu').numpy()[0])
        new_tokens, new_labels = [], []
        for token, label_idx in zip(tokens, label_indices[0]):
            if token.startswith("##"):
                new_tokens[-1] = new_tokens[-1] + token[2:]
            else:
                new_labels.append(label_idx)
                new_tokens.append(token)
        for token, label in zip(new_tokens, new_labels):
            if (label == 3):
                true_label.append(token)
            else:
                true_label.append('#')
        label = " ".join(true_label)
        label = label.replace(" ' s","'s")
        lst = label.split('#')
        p = self.clean_string(lst, sent)
        final_lst = []
        for ele in p:
            ele = re.sub(r'\(.*$', '', ele)
            final_lst.append(self.add_suffix(ele, sent))
        list_2 = []
        for ele in final_lst:
            ele = re.sub(r'\(.*$', '', ele)
            list_2.append(self.add_next_word(ele,sent))
        return list(filter(None, list_2))

    def multiline_data(self, text):
        text = text.replace('\n','.')
        names = []
        lst = text.split(".")
        for sent in lst:
            names.append(self.extract_location(sent))
        data = list(filter(None, names))
        l = []
        for place_list in data:
            for i in place_list:
                l.append(i + ', ' + self.city)
        return l

class PlaceFinder:
    def __init__(self, data):
        self.base_url = base_url
        self.api_key = api_key
        self.data = data

    def fetch_place_details(self,place_name):
      # Set up the parameters for the API request
      global result
      params = {
          'key': self.api_key,
          'input': place_name,
          'inputtype': 'textquery',
          'fields': 'place_id,name,formatted_address,rating,opening_hours,geometry,photos,types'
      }

      # Send the API request
      response = requests.get(self.base_url, params=params).json()

      # Check if the response contains any results
      if response['status'] == 'ZERO_RESULTS':
          result = ''
      else:
          result = response['candidates'][0]
          # Get the place ID of the first result (assuming it is the correct restaurant)
          place_id = response['candidates'][0]['place_id']

          # Make a request to the Places Details API to fetch the phone number
          details_url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=international_phone_number&key={api_key}'
          details_response = requests.get(details_url).json()

          # Extract the relevant details from the API response
          details = {}
          details['Name']= result['name']
          details['Address']= result['formatted_address']
          details['Rating'] = result.get('rating', 'N/A')
          details['Opening Hours'] =  result.get('opening_hours', 'N/A')
          details['Location']= result['geometry']['location']
          details['Types'] = result.get('types', 'N/A')[0]

          details['Phone'] = details_response['result'].get('international_phone_number', 'N/A')
          photos = []
          photo_references = result.get('photos', [])
          for photo_reference in photo_references:
              photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference['photo_reference']}&key={api_key}"
              photos.append(photo_url)
          details['Photos'] = photos

          return details

    
    def get_places_data(self):
        data = []
        for ele in self.data:
            data.append(self.fetch_place_details(ele))
        return data
   

class PlaceTagger:
    def __init__(self,frame):
        self.df = frame
        self.df['Tags'] = self.df['Tags'].astype(str)
        self.possible_tags = list(set(list(self.df['Tags'][:])))

        self.tag1_category = {}
        
        for i in range(len(self.df)):
            
            self.tag1_category[self.df['Tags'][i].lower()] = self.df['Category'][i]

        self.reconsider = ['point_of_interest', 'parking', 'neighborhood', 'premise', 'general_contractor',
                           'route', 'sublocality_level_1', 'sublocality_level_2',
                           'sublocality_level_3', 'locality', 'taxi_stand', 'travel_agency', 'campground',
                           'administrative_area_level_3', 'local_government_office', 'ward', 'colloquial_area']

        self.category_mapping = {
            'shopping_mall': 'shopping',
            'furniture_store': 'shopping',
            'clothing_store': 'shopping',
            'physiotherapist': 'self care',
            'jewelry_store': 'shopping',
            'store': 'shopping',
            'supermarket': 'shopping',
            'restaurant': 'food',
            'florist': 'shopping',
            'stadium': 'entertainment',
            'grocery_or_supermarket': 'shopping',
            'tourist_attraction': 'site-seeing',
            'university': 'site-seeing',
            'bakery': 'desserts',
            'food': 'food',
            'museum': 'site-seeing',
            'art_gallery': 'site-seeing',
            'natural_feature': 'site-seeing',
            'zoo': 'site-seeing',
            'hindu_temple': 'site-seeing',
            'casino': 'entertainment',
            'lodging': 'entertainment',
            'mosque': 'site-seeing',
            'park': 'site-seeing',
            'school': 'site-seeing',
            'spa': 'self care',
            'hair_care': 'self care',
            'beauty_salon': 'self care',
            'bar': 'bars and clubs',
            'cafe': 'cafe',
            'night_club': 'bars and clubs',
            'meal_takeaway': 'food',
            'book_store': 'shopping',
            'gym': 'self care',
            'meal_delivery': 'food',
            'movie_theater': 'entertainment',
            'bicycle_store': 'shopping',
            'shoe_store': 'shopping',
            'place_of_worship': 'site-seeing',
            'train_station': 'site-seeing',
            'church': 'site-seeing',
        }

    def pipeline(self, input_text, api_place_type):
        tags_category = None
        tags_from_name = []
        word_list = self.possible_tags
        matching_words = set()
        p = inflect.engine()  # Initialize the inflect engine

        # Dictionary mapping singular words to their plural forms
        plural_dict = {
            "mount": "Mountain"
        }

        input_words = [word.lower().replace(',', '') for word in input_text.split()]

        for word in word_list:
            if word.lower() in input_words:
                matching_words.add(word)
            elif p.plural(word.lower()) in input_words:
                matching_words.add(word)

        place_type = api_place_type
        if isinstance(place_type, str):  # Check if the value is a string
            if place_type in self.reconsider:
                for tag in list(matching_words):
                    if tag.lower() in self.tag1_category:
                        tags_category = self.tag1_category[tag.lower()]
                    elif 'food' in tag.lower() or 'cafe' in tag.lower() or 'desert' in tag.lower() or 'bar' in tag.lower():
                        tags_category = 'food'
                    else:
                        tags_category = 'site-seeing'

            if place_type in self.category_mapping:
                tags_category = self.category_mapping[place_type]
            elif 'food' in place_type or 'cafe' in place_type or 'desert' in place_type or 'bar' in place_type:
                tags_category = 'food'

        singular_words = []
        for word in matching_words:
            if word.lower() in plural_dict:
                singular_words.append(plural_dict[word.lower()])
            elif p.singular_noun(word):
                singular_words.append(p.singular_noun(word))
            else:
                singular_words.append(word)
        tags_from_name = list(set([word.lower() for word in singular_words]))

        if tags_category is not None:
            tag_list = tags_from_name + [tags_category]
        else:
            tag_list = tags_from_name

        return list(set([tag.lower() for tag in tag_list]))

    def all_tags(self, dataframe):
        names = dataframe['Name'][:]
        types = dataframe['Types'][:]
        all_tags = []
        for i in range(len(dataframe)):
            tags = self.pipeline(names[i], types[i])
            all_tags.append(tags)
        return all_tags
  
    
   
class PlaceDescriptionGenerator:
    def __init__(self, openai_key):
        self.openai_key = openai_key
        self.engine = engine
        openai.api_key = openai_key
        
        
    def get_description(self,place_name):
      # Set the prompt for the API
      prompt = """Get a 150 characters description about the place """ + place_name
     
      # Generate a response to the prompt
      response = openai.Completion.create(
          engine=self.engine,
          prompt=prompt,
          max_tokens=1024,
          n=1,
          stop=None,
          temperature=0.7,
      )

      # Extract the generated text from the response
      message = response.choices[0].text.strip()
      return message
    
    
      
    def list_des_data(self,data):
      all_data = []
      for place in data:
        info = {}
        des = self.get_description(place)
        info['Description'] = des
        all_data.append(info)
      return all_data

class GoogleSearchScraper:
    def __init__(self, query):
        self.base_url = f'https://www.google.com/search?q={query}'
        self.sites =  [
    'https://www.eater',
    'https://www.zagat',
    'https://www.theinfatuation',
    'https://www.thrillist',
    'https://www.timeout',
    'https://guide.michelin',
    'https://www.yelp',
    'https://www.tripadvisor',
    'https://www.opentable',
    'https://www.grubstreet',
    'https://www.foodandwine',
    'https://www.seriouseats',
    'https://www.thedailymeal',
    'https://www.gourmettraveller',
    'https://www.restaurantbusinessonline',
    'https://www.restaurantnews',
    'https://www.nrn',
    'https://www.foodrepublic',
    'https://www.bonappetit',
    'https://www.foodnetwork',
    'https://www.lonelyplanet',
    'https://www.nationalgeographic',
    'https://www.travelandleisure',
    'https://www.cntraveler',
    'https://www.fodors',
    'https://www.roughguides',
    'https://www.frommers',
    'https://theculturetrip',
    'https://www.afar',
    'https://www.atlasobscura',
    'https://thepointsguy',
    'https://www.jetsetter',
    'https://www.smartertravel',
    'https://www.travelzoo',
    'https://www.budgettravel',
    'https://www.tripsavvy',
    'https://www.insidertravel',
    'https://matadornetwork',
    'http://www.bbc',
    'https://www.nomadicmatt',
    'https://www.vogue.',
    'https://www.harpersbazaar.',
    'https://www.elle.',
    'https://www.wmagazine.',
    'https://www.instyle.',
    'https://www.refinery29.',
    'https://www.thecut.',
    'https://fashionista.',
    'https://www.whowhatwear.',
    'https://stylecaster.',
    'https://coveteur.',
    'https://www.highsnobiety.',
    'https://hypebeast.',
    'https://www.gq.',
    'https://www.esquire.',
    'https://www.complex.',
    'https://www.dazeddigital.',
    'https://i-d.vice.',
    'https://fashionmagazine.',
    'https://graziamagazine.'
]
    
    def scrape_google_search(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the desired information from the search results page
        # Replace this code with your specific scraping logic
        h2_element = soup.find_all("div", class_="egMi0 kCrYT")
        filtered_urls = []
        for ele in h2_element:
            h = ele.find('a')
            text = h['href']
            # Extract URLs using regular expressions
            match = re.search(r'/url\?q=(.*?)&', text)
            if match:
                url = match.group(1)
                # Filter the desired sites
                if any(site in url for site in self.sites):
                    info = {}
                    block = ele.find("div", class_="BNeawe vvjwJb AP7Wnd")
                    info['text'] = block.get_text()
                    info['link'] = url
                    filtered_urls.append(info)
    
        return filtered_urls
    
    def scrape_pages(self, num_pages):
        publications = []
        for page in range(num_pages):
            # Construct the URL for the current page
            if page == 0:
                url = self.base_url
            else:
                url = f'{self.base_url}&start={page * 10}'
            
            # Scrape data from the current page
            titles = self.scrape_google_search(url)
            publications += titles
        
        return publications
