#!/usr/bin/env python
import json
import csv
import os
import logging
from bs4 import BeautifulSoup
import cloudscraper
import argparse

keywords = {"mileage": ["miles"],
            "BHP": ["BHP"],
            "transmission": ["Automatic", "Manual"],
            "fuel": ["Petrol", "Diesel", "Electric", "Hybrid – Diesel/Electric Plug-in", "Hybrid – Petrol/Electric",
                     "Hybrid – Petrol/Electric Plug-in"],
            "owners": ["owners"],
            "body": ["Coupe", "Convertible", "Estate", "Hatchback", "MPV", "Pickup", "SUV", "Saloon"],
            "ULEZ": ["ULEZ"],
            "year": [" reg)"],
            "engine": ["engine"]}


def get_car_details(article):
    
    seller_info = article.find("h3", {"class": "product-card-seller-info__name atc-type-picanto"}).text.strip()
    if "Private" in seller_info:
        price_indicator = ""
    else:
        price_indicator = article.find("li", {"class": "badge-group__item"}).text.strip()
    car = {
            "name": article.find("h3", {"class": "product-card-details__title"}).text.strip(),
            "link": "https://www.autotrader.co.uk" + article.find("a", {"class": "tracking-standard-link"})["href"][: article.find("a", {"class": "tracking-standard-link"})["href"].find("?")],
            "price": article.find("div", {"class": "product-card-pricing__price"}).text.strip().replace(",", ""),
            "subtitle": article.find("p", {"class": "product-card-details__subtitle"}).text.strip().replace(",", ""),
            "price-indicator": price_indicator,
            "seller-info":  article.find("h3", {"class": "product-card-seller-info__name atc-type-picanto"}).text.strip().replace(",", ""),
        }
    # print(car)
    key_specs_bs_list = article.find("ul", {"class": "listing-key-specs"}).find_all("li")

    for key_spec_bs_li in key_specs_bs_list:

        key_spec_bs = key_spec_bs_li.text

        if any(keyword in key_spec_bs for keyword in keywords["mileage"]):
            car["mileage"] = int(key_spec_bs[:key_spec_bs.find(" miles")].replace(",", ""))
        elif any(keyword in key_spec_bs for keyword in keywords["BHP"]):
            car["BHP"] = int(key_spec_bs[:key_spec_bs.find("BHP")])
        elif any(keyword in key_spec_bs for keyword in keywords["transmission"]):
            car["transmission"] = key_spec_bs
        elif any(keyword in key_spec_bs for keyword in keywords["fuel"]):
            car["fuel"] = key_spec_bs
        elif any(keyword in key_spec_bs for keyword in keywords["owners"]):
            car["owners"] = int(key_spec_bs[:key_spec_bs.find(" owners")])
        elif any(keyword in key_spec_bs for keyword in keywords["body"]):
            car["body"] = key_spec_bs
        elif any(keyword in key_spec_bs for keyword in keywords["ULEZ"]):
            car["ULEZ"] = key_spec_bs
        elif any(keyword in key_spec_bs for keyword in keywords["year"]):
            car["year"] = key_spec_bs.split(' ')[0]
        elif key_spec_bs[1] == "." and key_spec_bs[3] == "L":
            car["engine"] = key_spec_bs
        else:
            logging.info(f'Unidentified information {key_spec_bs}')

    return car


def get_page_html(url, scraper, params={}, max_attempts_per_page=5):

    attempt = 1
    while attempt <= max_attempts_per_page:
        print(url)
        print(params)
        r = scraper.get(url, params=params)
        logging.info(f"Response: {r}")

        if r.status_code == 200:
            first_character = r.text[0]
            if first_character == '{':
                page_html = r.json()["html"]
            elif first_character == '<':
                page_html = r.text
                # print(r.text)
            else:
                raise Exception(f'Unknown start to response from {r.url}: {r.text[:100]}')
            s = BeautifulSoup(page_html, features="html.parser")
            return s

        else:  # if not successful (e.g. due to bot protection), log as an attempt
            attempt = attempt + 1
            logging.info(f"Exception. Starting attempt #{attempt} ")

    logging.info(f"Exception. All attempts exhausted for this page. Skipping to next page")

    return None


def get_cars(json_data, verbose=False):
    # 
    max_attempts_per_page=5
    if verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    logging.basicConfig(format='%(levelname)s:%(message)s', level=log_level)

    # To bypass Cloudflare protection
    scraper = cloudscraper.create_scraper()

    # Basic variables

    results = []
    n_this_year_results = 0
    # 
    # https://www.autotrader.co.uk/retailer/stock?sort=price-asc&page=1&dealer=10023353&onesearchad=Used&advertising-location=at_cars&advertising-location=at_profile_cars
    url_default = "https://www.autotrader.co.uk/retailer/stock"
    # 
    # Set up parameters for query to autotrader.co.uk
    search_params = {
                     "sort": "price-asc",
                     "dealer": "10023353",
                     "onesearchad": "Used",
                     "advertising-location": "at_cars",
                     "advertising-location": "at_profile_cars",
                     "make": "BMW",
                     }

    # if json_data["include_writeoff"] == "include":
    #     search_params["writeoff-categories"] = "on"
    # elif json_data["include_writeoff"] == "exclude":
    #     search_params["exclude-writeoff-categories"] = "on"
    # elif json_data["include_writeoff"] == "writeoff-only":
    #     search_params["only-writeoff-categories"] = "on"

    # year = json_data["min_year"]
    page = 1

    try:
        url = url_default
        params = search_params
        while url:
            s = get_page_html(url, scraper, params=params, max_attempts_per_page=max_attempts_per_page)
            if s:
                articles = s.find_all("article", attrs={"data-standout-type": ""})
                next_page_object = s.find(attrs={"class": "pagination--right__active"})
            else:
                articles = []
                next_page_object = None
            for article in articles:
                car = get_car_details(article)
                results.append(car)
                n_this_year_results = n_this_year_results + 1
            if next_page_object:
                page = page + 1
                url = next_page_object['href']
                params = {}
                logging.info(f"Car count: {len(results)}")
                logging.info("---------------------------------")
            else:
                url = None
                # logging.info(f"Found total {n_this_year_results} results for year {year} across {page} pages")

    except KeyboardInterrupt:
        pass

    return results


### Output functions ###

def save_csv(filename,results=None):
    csv_columns = ["name", "link", "price","subtitle","price-indicator","seller-info","mileage", "BHP", "transmission", "fuel", "owners", "body", "ULEZ",
                   "engine", "year"]
    if results:
        with open(filename, "w", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()
            for data in results:
                writer.writerow(data)


def save_json(filename,results=None ):
    if results:
        with open(filename, 'w') as f:
            json.dump(results, f, sort_keys=True, indent=4, separators=(',', ': '))

def parse_args():
    sample_input_json_file = """
    {
        "make" : "Audi",
        "model" : "A5",
        "model_variant" : "",
        "manufacturer_approved" : "",
        "maximum-mileage": 40000,
        "postcode" : "SW1A 0AA",
        "radius" : 1500,
        "min_year" : 2005,
        "max_year" : 2020,
        "include_writeoff" : "include",
        "max_attempts_per_page" : 5,
        "verbose" : "False"
}
    """
    # https://www.autotrader.co.uk/car-search?sort=datedesc&postcode=cv31nn&radius=1500&make=Audi&model=A4&include-delivery-option=on&year-to=2022&maximum-mileage=40000&ma=Y
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", help="output type csv or json", default="csv")
    parser.add_argument("--outfile", help="file prefix", default="scraper_output")
    parser.add_argument("--verbose", help="verbose mode", default=False)
    parser.add_argument("--inputfile", help="input file in json", default=sample_input_json_file)
    args = parser.parse_args()
    if not args.inputfile:
        print("ERROR: --inputfile is required ")
    return args

def main():
    
    args=parse_args()
    # print(args)
    input_file = args.inputfile
    
    json_data = {}
    # 
    if (os.path.exists(input_file)):
        with open(input_file,'r') as file:
            # print(file)
            json_data = json.load(file)
    else:
        json_data = input_file
    # 
    results = get_cars(json_data,args.verbose)
    if args.type == "json":
        if not ".json" in args.outfile:
            out_file = "{0}.{1}".format(args.outfile,args.type)
        else:
            out_file = args.outfile
        save_json(out_file,results)
    else:
        if not ".csv" in args.outfile:
            out_file = "{0}.{1}".format(args.outfile,args.type)
        else:
            out_file = args.outfile
        save_csv(out_file,results)

if __name__ == "__main__":
    main()