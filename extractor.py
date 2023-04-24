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
import requests

tokenizer = BertTokenizer.from_pretrained('bert-base-cased')
model = torch.load(r'/content/drive/MyDrive/BERT_text.pt')
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
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
        self.categories = ['Restaurant', 'Cafe', 'House', 'Barbecue', 'Bar', 'Pub', 'Palace', 'Kitchen', 'Club', 'Bakery', 'Shop', 'Room', 'Shack', 'Garden', 'Factory', 'Queen', 'Street', 'Mall', 'Park', 'Palace', 'Temple', 'Masjid', 'Dargah', 'Avenue', 'Gallery', 'Museum', 'Garden', 'Hotel', 'Lake', 'Fort', 'Beach', 'Mandir', 'Hill', 'Bhavan', 'Nation', 'World', 'Center','Pavilion', 'Bistro']

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
            final_lst.append(self.add_suffix(ele, sent))
        return list(filter(None, final_lst))

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
        
    def fetch_place_details(self, place):
        global result 
        # Set up the parameters for the API request
        params = {
            'key': self.api_key,
            'input': place,
            'inputtype': 'textquery',
            'fields': 'name,formatted_address,rating,opening_hours,geometry'
        }
        
        # Send the API request
        response = requests.get(self.base_url, params=params).json()

        # Check if the response contains any results
        if response['status'] == 'ZERO_RESULTS':
            print('No results found.')
            result = None
        else:
            # Get the details of the first result (assuming it is the correct restaurant)
            try: 
                result = response['candidates'][0]
            except:
                result = response
                
        details = {}
        try:
          details['Name'] = result['name']
          details['Address'] = result['formatted_address']
          details['Rating'] = result.get('rating', 'N/A')
          details['Opening Hours'] = result.get('opening_hours', 'N/A')
          details['Location'] = result['geometry']['location']
        except:
          pass
        
        return details
        
    
    def get_places_data(self):
        data = []
        for ele in self.data:
            data.append(self.fetch_place_details(ele))
        return data


    
    
class PlaceDescriptionGenerator:
    def __init__(self, openai_key):
        self.openai_key = openai_key
        self.engine = engine
        openai.api_key = openai_key
        
        
    def generate_description_and_tags(self, place_name):
        # Set the prompt for the API
        prompt = f"Generate a 300 character description and 3 relevant tags for {place_name}. I will give you one example, if the restaurant name is 'The Chocolate Room', the response should be of the format 'Description: The Chocolate Room, Mohali is a cozy little cafe that serves up some of the best chocolate desserts in town. With a menu that features both classic and innovative chocolate dishes, there's something for everyone at The Chocolate Room.Tags: Chocolate, Desserts, Cafe' only"
        
        # Generate a response to the prompt
        response = openai.Completion.create(
            engine=self.engine,
            prompt=prompt,
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0.5,
        )

        # Extract the generated text from the response
        message = response.choices[0].text.strip()

        description = re.findall(r'Description:(.+?)Tags:', message, flags=re.DOTALL)[0].strip()
        tags = re.findall(r'Tags:(.+)', message)[0].split(',')

        return description, tags

    def list_tag_data(self,data):
      all_data = []
      for place in data:
        info = {}
        info['Description'], info['Tags'] = self.generate_description_and_tags(place)
        all_data.append(info)
      return all_data

    def generate_description(self,place_name):
        # Set the prompt for the API
        prompt = f"Generate a 100 character description for {place_name}. I will give you one example, if the restaurant name is 'The Chocolate Room', the response should be of the format 'The Chocolate Room, Mohali is a cozy little cafe that serves up some of the best chocolate desserts in town. With a menu that features both classic and innovative chocolate dishes, there's something for everyone at The Chocolate Room."
        
        # Generate a response to the prompt
        response = openai.Completion.create(
            engine=self.engine,
            prompt=prompt,
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0.5,
        )

        # Extract the generated text from the response
        message = response.choices[0].text.strip()
        return message.replace('\n','')

    def list_description(self,data):
      all_description = []
      for place in data:
        info = {}
        info['Description'] = self.generate_description(place)
        all_description.append(info)
      return all_description
