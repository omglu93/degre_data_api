import requests
from main_flask import DegreeDataTable, LocationTable
from secret import API_TOKEN
import pandas as pd
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker 


class GetWeatherData():

    WEATHER_URL = "http://api.weatherapi.com/v1/history.json?"

    def __init__(self, location : str, time_period : str):

        self.location = location
        self.time_period = self._valid_date(time_period)

    
    def _valid_date(self, date: str) -> str:

        """Checks the validity of the date. The free version
        of the weather API only supports 7 days in historic
        data. Therefore, any call beyond the 7 days will be adjusted
        to be within the valid period (-7 days).
        """

        date = datetime.datetime.strptime(date, "%d-%m-%Y")
        current_time = datetime.datetime.now()

        if (date - current_time) < datetime.timedelta(days=7):
            
            date = current_time - datetime.timedelta(days=7)
            
        return date.date()

    def _get_data(self) -> pd.DataFrame:

        date_time = []
        temp = []

        date_list = self._generate_dates_between()

        for date in date_list:

            params = {"q": self.location, "dt": date}
            
            request_url = self.WEATHER_URL + f"key={API_TOKEN}"
            response = requests.request("GET", request_url, params=params)
            r = response.json()
         
            if "error" in r:
                print("Error in request")
                print(r["error"]["message"])
                
            else:
                for i in r["forecast"]["forecastday"][0]["hour"]:

                    date_time.append(i["time"])
                    temp.append(i["temp_c"])

        data_frame = pd.DataFrame({"datetime" : date_time, "temp_c" : temp})

        return data_frame

    def _generate_dates_between(self):

        days = datetime.datetime.now().date() - self.time_period
        date_list = []
        for i in range(days.days + 1):
            date_list.append(self.time_period + datetime.timedelta(i))

        
        return date_list


    def generate_dd(self):
        
        df = self._get_data()

        dd_calc = lambda x: (abs(x)+x)/2 

        df["CDD_10_5"] = dd_calc(df["temp_c"] - 10.5)
        df["CDD_15_5"] = dd_calc(df["temp_c"] - 15.5)
        df["CDD_18_5"] = dd_calc(df["temp_c"] - 18.5)

        df["HDD_10_5"] =  dd_calc(10.5 - df["temp_c"])
        df["HDD_15_5"] =  dd_calc(15.5 - df["temp_c"])
        df["HDD_18_5"] =  dd_calc(18.5 - df["temp_c"])

        df["Location"] = self.location

        return df


class UpdateDB():

    def __init__(self, dataframe : pd.DataFrame):
        self.dataframe = dataframe

    def _create_engine(self):

        engine = create_engine("sqlite:///degree_data.db", echo=False)

        return engine

    def _populate_tables(self):
        
        """ TODO Create a check on duplicate DD data 
        """

        DF_COLUMN_ORDER = [
                        "location_id", "datetime", "temp_c",
                        "CDD_10_5", "CDD_15_5", "CDD_18_5",
                        "HDD_10_5", "HDD_15_5", "HDD_18_5"
                        ]

        sql_engine = self._create_engine()
        Session = sessionmaker()
        Session.configure(bind=sql_engine)

        #### Location Table ####

        #location = self.dataframe["Location"].unique() #### Create a for loop that itterates over the values as city

        city = "London"
        
        try:
            so = Session()
            data_exists = so.query(LocationTable).filter(LocationTable.location == city).one()
            all_location = so.execute("SELECT * FROM location_table")
            
            # FK Mapper creation
            all_loc = {}
            for row in all_location:
                all_loc[row.location] = row.id
            
            if bool(data_exists.location) == False:
                so.add(LocationTable(location=city))

            self.dataframe["location_id"] = self.dataframe["Location"].map(all_loc)
            self.dataframe[DF_COLUMN_ORDER].to_sql("degree_data_table",
                                                    con=so.connection(),
                                                    if_exists="append",
                                                    index=False)

            so.commit()
        finally:
            so.close()

if __name__ == "__main__":

    #x = GetWeatherData("London", "14-12-2021").generate_dd()

    #UpdateDB()._populate_tables()

    # x = GetWeatherData("London", "14-12-2021").generate_dd()
    # x.to_excel("./test.xlsx")

    dd_data = pd.read_excel("./test.xlsx")

    UpdateDB(dd_data)._populate_tables()