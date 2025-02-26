#!/usr/bin/env python3
import os
import platform
import logging
import math
import time
from datetime import datetime
import re
from enum import Enum

import requests
from PIL import Image, ImageDraw, ImageFont

import gpiod
from inky.inky_uc8159 import (
    BLACK,
    WHITE,
    GREEN,
    RED,
    YELLOW,
    ORANGE,
    BLUE,
    DESATURATED_PALETTE as color_palette,
)

# the auto setup does for some reason do not work on some
# raspberries - so using the explicit imports
# from inky.auto import auto
from inky import Inky7Colour as Inky_Impressions_57
from inky import Inky_Impressions_7 as Inky_Impressions_73


DEBUG = bool(os.environ.get('DEBUG'))
logging.basicConfig(level=logging.INFO)

saturation = 0.5

tmpfs_path = "/tmp/" if platform.system() == "Darwin" else "/dev/shm/"

# font file path(Adjust or change whatever you want)
if not os.environ.get('WI_DIR'):
    raise TypeError('Missing WI_DIR ENVIRONMENT variable')
os.chdir(r"{}".format(os.environ.get('WI_DIR')))
project_root = os.getcwd()

unit_imperial = "imperial"

colorMap = {
    "01d": ORANGE,  # clear sky
    "01n": YELLOW,
    "02d": BLACK,  # few clouds
    "02n": BLACK,
    "03d": BLACK,  # scattered clouds
    "03n": BLACK,
    "04d": BLACK,  # broken clouds
    "04n": BLACK,
    "09d": BLACK,  # shower rain
    "09n": BLACK,
    "10d": BLUE,  # rain
    "10n": BLUE,
    "11d": RED,  # thunderstorm
    "11n": RED,
    "13d": BLUE,  # snow
    "13n": BLUE,
    "50d": BLACK,  # fog
    "50n": BLACK,
    "sunrise": BLACK,
    "sunset": BLACK,
}
# icon name to weather icon mapping
iconMap = {
    "01d": "",  # clear sky
    "01n": "",
    "02d": "",  # few clouds
    "02n": "",
    "03d": "",  # scattered clouds
    "03n": "",
    "04d": "",  # broken clouds
    "04n": "",
    "09d": "",  # shower rain
    "09n": "",
    "10d": "",  # rain
    "10n": "",
    "11d": "",  # thunderstorm
    "11n": "",
    "13d": "",  # snow
    "13n": "",
    "50d": "",  # fog
    "50n": "",
    "clock0": "",  # same as 12
    "clock1": "",
    "clock2": "",
    "clock3": "",
    "clock4": "",
    "clock5": "",
    "clock6": "",
    "clock7": "",
    "clock8": "",
    "clock9": "",
    "clock10": "",
    "clock11": "",
    "clock12": "",
    "celsius": "",
    "fahrenheit": "",
    "sunrise": "",
    "sunset": "",
}


def getTranslation(lang, value):
    if lang == "EN":
        return value
    else:
        try:
            translations = {
                "January": "Januar",
                "February": "Februar",
                "March": "März",
                "April": "April",
                "May": "Mai",
                "June": "Juni",
                "July": "Juli",
                "August": "August",
                "September": "September",
                "October": "Oktober",
                "November": "November",
                "December": "Dezember",
                "Mon": "Mo",
                "Tue": "Di",
                "Wed": "Mi",
                "Thu": "Do",
                "Fri": "Fr",
                "Sat": "Sa",
                "Sun": "So",
                "Temperature": "Temperatur",
                "Feels like": "Gefühlt",
                "Pressure": "Druck",
                "Rain": "Regen",
                "AM": "00:00",
                "PM": "12:00",
                "clear sky": "klare Sicht",
                "few clouds": "Wolkig",
                "scattered clouds": "Bewölkt",
                "broken clouds": "Leicht Bewölkt",
                "overcast clouds": "Bedeckt",
                "shower rain": "Starker Regen",
                "rain": "Regen",
                "thunderstorm": "Gewitter",
                "snow": "Schnee",
                "fog": "Nebel",
            }
            return translations[value]
        except KeyError:
            return value


def getCanvasSize(inky_type):
    if inky_type == "57":
        return (600, 448)
    elif inky_type == "73":
        return (800, 480)
    else:
        raise TypeError("Invalid Inky Type")


def getWeatherIconOffset(inky_type):
    # inch-size - 130
    if inky_type == "57":
        return 440
    elif inky_type == "73":
        return 600
    else:
        raise TypeError("Invalid Inky Type")
    
def getGraphSize(inky_type):
    if inky_type == "57":
        return (1.1, 8.4)
    elif inky_type == "73":
        return (1.6, 11.0)
    else:
        raise TypeError("Invalid Inky Type")

def getURIByType(endpoint, lat, lon, api_key, unit):
    if endpoint == "onecall":
        return (
            "https://api.openweathermap.org/data/3.0/onecall?&lat="
            + lat
            + "&lon="
            + lon
            + "&appid="
            + api_key
            + "&exclude=daily"
            + "&units="
            + unit
        )
    elif endpoint == "rain":
        return (
            "https://api.openweathermap.org/data/2.5/forecast?lat="
            + lat
            + "&lon="
            + lon
            + "&appid="
            + api_key
            + "&units="
            + unit
            + "&cnt=17" # limit to 48h/3h + 1 to adjust with 48h forecast from other api
        )
    else:
        raise TypeError("Invalid URI endpoint")

def getRangeNumber(idx):
    # based on 3h forecast for rain
    # returns the next idx only every 3rd time
    return math.floor(idx / 3)


# empty structure
class forecastInfo:
    pass


class weatherInfomation(object):
    def __init__(self):
        # load configuration from config.txt using configparser
        import configparser

        self.config = configparser.ConfigParser()
        try:
            self.config.read_file(open(project_root + "/config.txt"))
            self.lat = self.config.get("openweathermap", "LAT", raw=False)
            self.lon = self.config.get("openweathermap", "LON", raw=False)
            self.mode = self.config.get("openweathermap", "mode", raw=False)
            self.forecast_interval = self.config.get(
                "openweathermap", "FORECAST_INTERVAL", raw=False
            )
            self.api_key = self.config.get("openweathermap", "API_KEY", raw=False)
            
            self.unit = self.config.get("openweathermap", "TEMP_UNIT", raw=False)
            self.cold_temp = float(
                self.config.get("openweathermap", "cold_temp", raw=False)
            )
            self.hot_temp = float(
                self.config.get("openweathermap", "hot_temp", raw=False)
            )
            
            self.lang = self.config.get("openweathermap", "LANG")
            self.inky_size = self.config.get("openweathermap", "INKY_SIZE")
            self.mode2_rain = self.config.get("openweathermap", "MODE2_RAIN")
            self.mode2_pressure = self.config.get("openweathermap", "MODE2_PRESSURE")

            # api uri handling & data-fetching
            # API documentation at:
            #   onecall: https://openweathermap.org/api/one-call-api
            #   forecast: https://openweathermap.org/forecast5
            self.forecast_api_uri_onecall = getURIByType("onecall", self.lat, self.lon, self.api_key, self.unit)
            if self.mode2_rain == 'true':
                self.forecast_api_uri_rain = getURIByType("rain", self.lat, self.lon, self.api_key, self.unit)

            self.loadWeatherData(True if self.mode2_rain == 'true' else False)
        except:
            self.one_time_message = (
                "Configuration file is not found or settings are wrong.\nplease check the file : "
                + project_root
                + "/config.txt\n\nAlso check your internet connection."
            )
            return

        # load one time messge and remove it from the file. one_time_message can be None.
        try:
            self.one_time_message = self.config.get(
                "openweathermap", "one_time_message", raw=False
            )
            self.config.set("openweathermap", "one_time_message", "")
            # remove it.
            with open(project_root + "/config.txt", "w") as configfile:
                self.config.write(configfile)
        except:
            self.one_time_message = ""
            pass

    def loadWeatherData(self, load_rain=False):
        logging.info('Request weather info START')

        self.weatherInfo = requests.get(self.forecast_api_uri_onecall).json()
        if load_rain is True:
            self.weatherInfoRain = requests.get(self.forecast_api_uri_rain).json()
        logging.info('Request weather info END')


class fonts(Enum):
    thin = project_root + "/fonts/Roboto-Thin.ttf"
    light = project_root + "/fonts/Roboto-Light.ttf"
    normal = project_root + "/fonts/Roboto-Black.ttf"
    icon = project_root + "/fonts/weathericons-regular-webfont.ttf"


def getFont(type, fontsize=12):
    return ImageFont.truetype(type.value, fontsize)


def getFontColor(temp, wi):
    if temp < wi.cold_temp:
        return (0, 0, 255)
    if temp > wi.hot_temp:
        return (255, 0, 0)
    return getDisplayColor(BLACK)


def getUnitSign(unit):
    if unit == unit_imperial:
        return iconMap["fahrenheit"]

    return iconMap["celsius"]


# return rgb in 0 ~ 255
def getDisplayColor(color):
    return tuple(color_palette[color])


def getTempretureString(temp):
    formattedString = "%0.0f" % temp
    if formattedString == "-0":
        return "0"
    else:
        return formattedString


# return color rgb in 0 ~ 1.0 scale
def getGraphColor(color):
    r = color_palette[color][0] / 255
    g = color_palette[color][1] / 255
    b = color_palette[color][2] / 255
    return (r, g, b)


# draw current weather and forecast into canvas
def drawWeather(wi, cv):
    draw = ImageDraw.Draw(cv)
    width, height = cv.size

    # one time message
    if hasattr(wi, "weatherInfo") is False:
        draw.rectangle((0, 0, width, height), fill=getDisplayColor(ORANGE))
        draw.text(
            (20, 70),
            "",
            getDisplayColor(BLACK),
            anchor="lm",
            font=getFont(fonts.icon, fontsize=130),
        )
        draw.text(
            (150, 80),
            "Weather information is not available at this time.",
            getDisplayColor(BLACK),
            anchor="lm",
            font=getFont(fonts.normal, fontsize=18),
        )
        draw.text(
            (width / 2, height / 2),
            wi.one_time_message,
            getDisplayColor(BLACK),
            anchor="mm",
            font=getFont(fonts.normal, fontsize=16),
        )
        return
    draw.text(
        (width - 10, 2),
        wi.one_time_message,
        getDisplayColor(BLACK),
        anchor="ra",
        font=getFont(fonts.normal, fontsize=12),
    )

    temp_cur = wi.weatherInfo["current"]["temp"]
    temp_cur_feels = wi.weatherInfo["current"]["feels_like"]
    icon = str(wi.weatherInfo["current"]["weather"][0]["icon"])
    description = wi.weatherInfo["current"]["weather"][0]["description"]
    wi.weatherInfo["current"]["humidity"]
    pressure = wi.weatherInfo["current"]["pressure"]
    epoch = int(wi.weatherInfo["current"]["dt"])
    # snow = wi.weatherInfo[u'current'][u'snow']
    # dateString = time.strftime("%B %-d", time.localtime(epoch))
    monthString = time.strftime("%B", time.localtime(epoch))
    dayString = time.strftime("%-d", time.localtime(epoch))
    weekDayString = time.strftime("%a", time.localtime(epoch))
    time.strftime("%w", time.localtime(epoch))

    # date
    draw.text(
        (15, 5),
        getTranslation(wi.lang, monthString) + " " + dayString,
        getDisplayColor(BLACK),
        font=getFont(fonts.normal, fontsize=64),
    )
    draw.text(
        (width - 8, 5),
        getTranslation(wi.lang, weekDayString),
        getDisplayColor(BLACK),
        anchor="ra",
        font=getFont(fonts.normal, fontsize=64),
    )

    offsetX = 10
    offsetY = 40

    # Draw temperature string
    tempOffset = 20
    temperatureTextWidth = draw.textlength(
        getTempretureString(temp_cur), font=getFont(fonts.normal, fontsize=120)
    )
    if temperatureTextWidth < 71:
        # when the temp string is a bit short.
        tempOffset = 45
    draw.text(
        (5 + offsetX, 35 + offsetY),
        getTranslation(wi.lang, "Temperature"),
        getDisplayColor(BLACK),
        font=getFont(fonts.light, fontsize=24),
    )
    draw.text(
        (tempOffset + offsetX, 50 + offsetY),
        getTempretureString(temp_cur),
        getFontColor(temp_cur, wi),
        font=getFont(fonts.normal, fontsize=120),
    )
    draw.text(
        (temperatureTextWidth + 10 + tempOffset + offsetX, 85 + offsetY),
        getUnitSign(wi.unit),
        getFontColor(temp_cur, wi),
        anchor="la",
        font=getFont(fonts.icon, fontsize=80),
    )

    # draw current weather icon
    draw.text(
        (getWeatherIconOffset(wi.inky_size) + offsetX, 40 + offsetY),
        iconMap[icon],
        getDisplayColor(colorMap[icon]),
        anchor="ma",
        font=getFont(fonts.icon, fontsize=160),
    )

    # weather description below weekday string
    draw.text(
        (width - 8, 35 + offsetY),
        getTranslation(wi.lang, description),
        getDisplayColor(BLACK),
        anchor="ra",
        font=getFont(fonts.light, fontsize=24),
    )

    # feels like
    draw.text(
        (5 + offsetX, 175 + 40),
        getTranslation(wi.lang, "Feels like"),
        getDisplayColor(BLACK),
        font=getFont(fonts.light, fontsize=24),
    )
    draw.text(
        (10 + offsetX, 200 + 40),
        getTempretureString(temp_cur_feels),
        getFontColor(temp_cur_feels, wi),
        font=getFont(fonts.normal, fontsize=50),
    )
    feelslikeTextWidth = draw.textlength(
        getTempretureString(temp_cur_feels), font=getFont(fonts.normal, fontsize=50)
    )
    draw.text(
        (feelslikeTextWidth + 20 + offsetX, 200 + 40),
        getUnitSign(wi.unit),
        getFontColor(temp_cur_feels, wi),
        anchor="la",
        font=getFont(fonts.icon, fontsize=50),
    )

    # Pressure
    draw.text(
        (feelslikeTextWidth + 85 + offsetX, 175 + 40),
        getTranslation(wi.lang, "Pressure"),
        getDisplayColor(BLACK),
        font=getFont(fonts.light, fontsize=24),
    )
    draw.text(
        (feelslikeTextWidth + 90 + offsetX, 200 + 40),
        "%d" % pressure,
        getDisplayColor(BLACK),
        font=getFont(fonts.normal, fontsize=50),
    )
    pressureTextWidth = draw.textlength(
        "%d" % pressure, font=getFont(fonts.normal, fontsize=50)
    )
    draw.text(
        (feelslikeTextWidth + pressureTextWidth + 95 + offsetX, 224 + 40),
        "hPa",
        getDisplayColor(BLACK),
        font=getFont(fonts.normal, fontsize=22),
    )

    offsetY = 210

    # MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1
    # MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1 MODE 1
    # When alerts are in effect, show it to forecast area.
    if wi.mode == "1" and "alerts" in wi.weatherInfo:
        alertInEffectString = time.strftime(
            "%B %-d, %H:%m %p", time.localtime(wi.weatherInfo["alerts"][0]["start"])
        )

        # remove "\n###\n" and \n\n
        desc = wi.weatherInfo["alerts"][0]["description"].replace("\n###\n", "")
        desc = desc.replace("\n\n", "")
        desc = desc.replace("https://", "")  # remove https://
        desc = re.sub(r"([A-Za-z]*:)", "\n\g<1>", desc)
        desc = re.sub(r"((?=.{90})(.{0,89}([\.[ ]|[ ]))|.{0,89})", "\g<1>\n", desc)
        desc = desc.replace("\n\n", "")

        draw.text(
            (5 + offsetX, 215),
            wi.weatherInfo["alerts"][0]["event"].capitalize(),
            getDisplayColor(RED),
            anchor="la",
            font=getFont(fonts.light, fontsize=24),
        )
        draw.text(
            (5 + offsetX, 240),
            alertInEffectString + "/" + wi.weatherInfo["alerts"][0]["sender_name"],
            getDisplayColor(BLACK),
            font=getFont(fonts.normal, fontsize=12),
        )

        draw.text(
            (5 + offsetX, 270),
            desc,
            getDisplayColor(RED),
            anchor="la",
            font=getFont(fonts.normal, fontsize=14),
        )
        return

    # MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2
    # MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2 MODE 2
    # Graph mode
    if wi.mode == "2":
        import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        import numpy as np

        forecastRange = 47
        graph_size = getGraphSize(wi.inky_size)
        graph_height = graph_size[0]
        graph_width = graph_size[1]
        xarray = []
        tempArray = []
        feelsArray = []
        pressureArray = []
        rainArray = []

        # "weather": [
        #     {
        #         "id": 500,
        #         "main": "Rain",
        #         "description": "light rain",
        #         "icon": "10n"
        #     }
        # ],

        try:
            for fi in range(forecastRange):
                finfo = forecastInfo()
                finfo.time_dt = wi.weatherInfo["hourly"][fi]["dt"]
                finfo.time = time.strftime("%-I %p", time.localtime(finfo.time_dt))
                finfo.temp = wi.weatherInfo["hourly"][fi]["temp"]
                finfo.feels_like = wi.weatherInfo["hourly"][fi]["feels_like"]
                finfo.humidity = wi.weatherInfo["hourly"][fi]["humidity"]
                finfo.pressure = wi.weatherInfo["hourly"][fi]["pressure"]
                if wi.mode2_rain == 'true':
                    finfo.rain = wi.weatherInfoRain["list"][getRangeNumber(fi)].get("rain", { "3h": 0.0 })
                else:
                    finfo.rain = { "3h": 0.0 }
                finfo.icon = wi.weatherInfo["hourly"][fi]["weather"][0]["icon"]
                # print(wi.weatherInfo[u'hourly'][fi][u'snow'][u'1h']) # mm  / you may get 8 hours maximum
                
                xarray.append(finfo.time_dt)
                tempArray.append(finfo.temp)
                feelsArray.append(finfo.feels_like)
                pressureArray.append(finfo.pressure)
                rainArray.append(finfo.rain["3h"])
        except IndexError:
            # The weather forecast API is supposed to return 48 forecasts, but it may return fewer than 48.
            errorMessage = (
                "Weather API returns limited hourly forecast(" + str(len(xarray)) + ")"
            )
            draw.text(
                (width - 10, height - 2),
                errorMessage,
                getDisplayColor(ORANGE),
                anchor="ra",
                font=getFont(fonts.normal, fontsize=12),
            )
            pass
          
        if wi.mode2_pressure == "true":
            # graph-pressure
            fig = plt.figure()
            fig.set_figheight(graph_height)
            fig.set_figwidth(graph_width)
            plt.plot(
                xarray, pressureArray, linewidth=3, color=getGraphColor(RED)
            )  # RGB in 0~1.0
            # plt.plot(xarray, pressureArray)
            # annot_max(np.array(xarray),np.array(tempArray))
            # annot_max(np.array(xarray),np.array(pressureArray))
            plt.axis("off")
            plt.gca()
            airPressureMin = 990
            airPressureMax = 1020
            if min(pressureArray) < airPressureMin - 2:
                airPressureMin = min(pressureArray) + 2
            if max(pressureArray) > airPressureMax - 2:
                airPressureMax = max(pressureArray) + 2

            plt.ylim(airPressureMin, airPressureMax)

            plt.savefig(tmpfs_path + "pressure.png", bbox_inches="tight", transparent=True)
            tempGraphImage = Image.open(tmpfs_path + "pressure.png")
            cv.paste(tempGraphImage, (-35, 330), tempGraphImage)

        # draw temp and feels like in one figure
        fig = plt.figure()
        fig.set_figheight(graph_height)
        fig.set_figwidth(graph_width)
        plt.plot(
            xarray, feelsArray, linewidth=3, color=getGraphColor(GREEN), linestyle=":"
        )  # RGB in 0~1.0
        plt.axis("off")
        plt.plot(xarray, tempArray, linewidth=3, color=getGraphColor(ORANGE))

        for idx in range(1, len(xarray)):
            h = time.strftime("%-I", time.localtime(xarray[idx]))
            if h == "0" or h == "12":
                plt.axvline(x=xarray[idx], color="black", linestyle=":")
                posY = np.array(tempArray).max() + 1
                plt.text(
                    xarray[idx - 1],
                    posY,
                    getTranslation(
                        wi.lang, time.strftime("%p", time.localtime(xarray[idx]))
                    ),
                )
        plt.axis("off")
        plt.savefig(tmpfs_path + "temp.png", bbox_inches="tight", transparent=True)
        tempGraphImage = Image.open(tmpfs_path + "temp.png")
        cv.paste(tempGraphImage, (-35, 300), tempGraphImage)

        # rain
        if wi.mode2_rain == "true":
            fig = plt.figure()
            fig.set_figheight(graph_height)
            fig.set_figwidth(graph_width)
            plt.plot(
                xarray, rainArray, linewidth=3, color=getGraphColor(BLUE)
            )  # RGB in 0~1.0
            plt.axis("off")
            plt.gca()
            plt.savefig(tmpfs_path + "rain.png", bbox_inches="tight", transparent=True)
            tempGraphImage = Image.open(tmpfs_path + "rain.png")
            cv.paste(tempGraphImage, (-35, 320), tempGraphImage)

        # draw labels
        presure_offset = 135 if wi.mode2_pressure == "true" else 0
        # label.pressure
        if wi.mode2_pressure == "true":
            draw.rectangle((10, 460, 25, 476), fill=getDisplayColor(RED))
            draw.text(
                (20 + offsetX, 458),
                getTranslation(wi.lang, "Pressure"),
                getDisplayColor(BLACK),
                font=getFont(fonts.normal, fontsize=16),
            )

        # label.temp
        draw.rectangle((10 + presure_offset, 460, 25 + presure_offset, 476), fill=getDisplayColor(ORANGE))
        draw.text(
            (20 + offsetX + presure_offset, 458),
            getTranslation(wi.lang, "Temp"),
            getDisplayColor(BLACK),
            font=getFont(fonts.normal, fontsize=16),
        )

        # label.feels-like
        draw.rectangle((145 + presure_offset, 460, 160 + presure_offset, 476), fill=getDisplayColor(GREEN))
        draw.text(
            (155 + offsetX + presure_offset, 458),
            getTranslation(wi.lang, "Feels like"),
            getDisplayColor(BLACK),
            font=getFont(fonts.normal, fontsize=16),
        )
        
        # label.rain
        if wi.mode2_rain == "true":
            draw.rectangle((280 + presure_offset, 460, 295 + presure_offset, 476), fill=getDisplayColor(BLUE))
            draw.text(
                (290 + offsetX + presure_offset, 458),
                getTranslation(wi.lang, "Rain"),
                getDisplayColor(BLACK),
                font=getFont(fonts.normal, fontsize=16),
            )
        return

    # MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3
    # MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3 MODE 3
    # Sunrise / Sunset mode
    if wi.mode == "3":
        sunrise = wi.weatherInfo["current"]["sunrise"]
        sunset = wi.weatherInfo["current"]["sunset"]

        sunriseFormatted = datetime.fromtimestamp(sunrise).strftime("%#I:%M %p")
        sunsetFormatted = datetime.fromtimestamp(sunset).strftime("%#I:%M %p")

        # print([sunriseFormatted, sunsetFormatted])

        columnWidth = width / 2
        textColor = (50, 50, 50)
        # center = column width / 2 - (text_width * .5)
        # measure sunrise
        sunrise_width, _ = getFont(fonts.normal, fontsize=16).getsize("Sunrise")
        sunriseXOffset = (columnWidth / 2) - (sunrise_width * 0.5)

        sunriseFormatted_width, _ = getFont(fonts.normal, fontsize=12).getsize(
            sunriseFormatted
        )
        sunriseFormattedXOffset = (columnWidth / 2) - (sunriseFormatted_width * 0.5)

        sunriseIcon_width, _ = getFont(fonts.icon, fontsize=90).getsize(
            iconMap["sunrise"]
        )
        sunriseIconXOffset = (columnWidth / 2) - (sunriseIcon_width * 0.5)

        draw.text(
            (sunriseFormattedXOffset, offsetY + 220),
            sunriseFormatted,
            textColor,
            anchor="la",
            font=getFont(fonts.normal, fontsize=12),
        )
        draw.text(
            (sunriseIconXOffset, offsetY + 90),
            iconMap["sunrise"],
            getDisplayColor(colorMap["sunrise"]),
            anchor="la",
            font=getFont(fonts.icon, fontsize=90),
        )
        draw.text(
            (sunriseXOffset, offsetY + 200),
            "Sunrise",
            textColor,
            anchor="la",
            font=getFont(fonts.normal, fontsize=16),
        )

        sunset_width, _ = getFont(fonts.normal, fontsize=16).getsize("sunset")
        sunsetXOffset = columnWidth + (columnWidth / 2) - (sunset_width * 0.5)

        sunsetFormatted_width, _ = getFont(fonts.normal, fontsize=12).getsize(
            sunsetFormatted
        )
        sunsetFormattedXOffset = (
            columnWidth + (columnWidth / 2) - (sunsetFormatted_width * 0.5)
        )

        sunsetIcon_width, _ = getFont(fonts.icon, fontsize=90).getsize(
            iconMap["sunset"]
        )
        sunsetIconXOffset = columnWidth + (columnWidth / 2) - (sunsetIcon_width * 0.5)

        draw.text(
            (sunsetFormattedXOffset, offsetY + 220),
            sunsetFormatted,
            textColor,
            anchor="la",
            font=getFont(fonts.normal, fontsize=12),
        )
        draw.text(
            (sunsetIconXOffset, offsetY + 90),
            iconMap["sunset"],
            getDisplayColor(colorMap["sunset"]),
            anchor="la",
            font=getFont(fonts.icon, fontsize=90),
        )
        draw.text(
            (sunsetXOffset, offsetY + 200),
            "Sunset",
            textColor,
            anchor="la",
            font=getFont(fonts.normal, fontsize=16),
        )

        return

    # MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4
    # MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4 MODE 4
    if wi.mode == "4":
        import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        import numpy as np

        # import datetime

        def minutes_since(timestamp):
            dt = datetime.fromtimestamp(timestamp)
            timestamp_minutes_since_midnight = dt.hour * 60 + dt.minute
            return timestamp_minutes_since_midnight

        # icon font setup
        icon_font = getFont(fonts.icon, fontsize=12)
        icon_prop = fm.FontProperties(fname=icon_font.path)
        text_font = getFont(fonts.normal, fontsize=12)
        text_prop = fm.FontProperties(fname=text_font.path)

        graph_height = 1.1
        graph_width = 8.4

        x = [i for i in range(24)]
        # y = [math.sin(math.pi * i / 12) for i in x]
        y = [math.cos((i / 12 - 1) * math.pi) for i in x]

        fig = plt.figure()
        fig.set_figheight(graph_height)
        fig.set_figwidth(graph_width)

        plt.xlim(0, 23)
        plt.ylim(-1.2, 1.2)
        # add labels and title
        # plt.xlabel("Hour of Day")
        # plt.ylabel("Sun Elevation")
        plt.title("")

        # add sunrise and sunset lines
        sunrise_timestamp = wi.weatherInfo["current"]["sunrise"]
        sunset_timestamp = wi.weatherInfo["current"]["sunset"]
        sunrise_time = minutes_since(sunrise_timestamp)
        sunset_time = minutes_since(sunset_timestamp)
        sunrise_hour = sunrise_time / 60
        sunset_hour = sunset_time / 60
        sunriseFormatted = datetime.fromtimestamp(sunrise_timestamp).strftime(
            "%#I:%M %p"
        )
        sunsetFormatted = datetime.fromtimestamp(sunset_timestamp).strftime("%#I:%M %p")

        plt.axvline(x=sunrise_hour, color="blue", linestyle="--")
        plt.axvline(x=sunset_hour, color="blue", linestyle="--")

        plt.text(
            sunrise_hour - 0.35,
            1.35,
            iconMap["sunrise"],
            fontproperties=icon_prop,
            ha="right",
            va="top",
            color=getGraphColor(YELLOW),
        )
        plt.text(
            sunrise_hour - 0.3,
            1.3,
            iconMap["sunrise"],
            fontproperties=icon_prop,
            ha="right",
            va="top",
            color=getGraphColor(BLUE),
        )

        plt.text(
            sunset_hour + 0.35,
            1.35,
            iconMap["sunset"],
            fontproperties=icon_prop,
            ha="left",
            va="top",
            color=getGraphColor(YELLOW),
        )
        plt.text(
            sunset_hour + 0.3,
            1.3,
            iconMap["sunset"],
            fontproperties=icon_prop,
            ha="left",
            va="top",
            color=getGraphColor(BLUE),
        )
        plt.text(
            sunrise_hour - 0.3,
            0.8,
            sunriseFormatted,
            ha="right",
            va="top",
            fontproperties=text_prop,
            rotation="horizontal",
            color=getGraphColor(BLUE),
        )
        plt.text(
            sunset_hour + 0.3,
            0.8,
            sunsetFormatted,
            ha="left",
            va="top",
            fontproperties=text_prop,
            rotation="horizontal",
            color=getGraphColor(BLUE),
        )

        normal = getFont(fonts.normal, fontsize=12)
        plt.rcParams["font.family"] = normal.getname()

        plt.plot(x, y, linewidth=3, color=getGraphColor(RED))  # RGB in 0~1.0
        # plt.plot(xarray, pressureArray)
        # annot_max(np.array(xarray),np.array(tempArray))
        # annot_max(np.array(xarray),np.array(pressureArray))
        plt.axis("off")

        plt.savefig(tmpfs_path + "day.png", bbox_inches="tight", transparent=True)
        tempGraphImage = Image.open(tmpfs_path + "day.png")
        cv.paste(tempGraphImage, (-35, 300), tempGraphImage)

        return

    forecastIntervalHours = int(wi.forecast_interval)
    forecastRange = 4
    for fi in range(forecastRange):
        finfo = forecastInfo()
        finfo.time_dt = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["dt"]
        finfo.time = time.strftime("%-I %p", time.localtime(finfo.time_dt))
        finfo.timeIn12h = time.strftime("clock%-I", time.localtime(finfo.time_dt))
        # finfo.ampm     = time.strftime('%p', time.localtime(finfo.time_dt))
        # finfo.time     = time.strftime('%-I', time.localtime(finfo.time_dt))
        finfo.timePfx = time.strftime("%p", time.localtime(finfo.time_dt))
        finfo.temp = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["temp"]
        finfo.feels_like = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["feels_like"]
        finfo.humidity = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["humidity"]
        finfo.pressure = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["pressure"]
        finfo.icon = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["weather"][0]["icon"]
        finfo.description = wi.weatherInfo["hourly"][
            fi * forecastIntervalHours + forecastIntervalHours
        ]["weather"][0][
            "description"
        ]  # show the first

        columnWidth = width / forecastRange
        textColor = (50, 50, 50)
        # Clock icon for the time.(Not so nice.)
        # draw.text((20 + (fi * columnWidth),  offsetY + 90), iconMap[finfo.timeIn12h], textColor, anchor="ma",font =ImageFont.truetype(project_root + "fonts/weathericons-regular-webfont.ttf", 35))
        draw.text(
            (30 + (fi * columnWidth), offsetY + 220),
            finfo.time,
            textColor,
            anchor="la",
            font=getFont(fonts.normal, fontsize=12),
        )
        draw.text(
            (120 + (fi * columnWidth), offsetY + 220),
            ("%2.1f" % finfo.temp),
            textColor,
            anchor="ra",
            font=getFont(fonts.normal, fontsize=12),
        )

        draw.text(
            ((columnWidth / 2) + (fi * columnWidth), offsetY + 200),
            finfo.description,
            textColor,
            anchor="ma",
            font=getFont(fonts.normal, fontsize=16),
        )
        draw.text(
            (70 + (fi * columnWidth), offsetY + 90),
            iconMap[finfo.icon],
            getDisplayColor(colorMap[finfo.icon]),
            anchor="ma",
            font=getFont(fonts.icon, fontsize=80),
        )


def annot_max(x, y, ax=None):
    xmax = x[np.argmax(y)]
    ymax = y.max()
    maxTime = time.strftime("%b %-d,%-I%p", time.localtime(xmax))
    text = maxTime + " {:.1f}C".format(ymax)
    if not ax:
        ax = plt.gca()
    bbox_props = dict(boxstyle="square,pad=0.3", fc="w", ec="k", lw=0.72)
    arrowprops = dict(arrowstyle="->", connectionstyle="angle,angleA=0,angleB=60")
    kw = dict(
        xycoords="data",
        textcoords="axes fraction",
        arrowprops=arrowprops,
        bbox=bbox_props,
        ha="right",
        va="top",
    )

    fpath = "/home/pi/inky/weather-impression/fonts/Roboto-Black.ttf"
    prop = fm.FontProperties(fname=fpath)
    ax.annotate(text, xy=(xmax, ymax), xytext=(0.93, 1.56), fontproperties=prop, **kw)


def initGPIO():
    chip = gpiod.chip(0)  # 0 chip
    pin = 4
    gpiod_pin = chip.get_line(pin)
    config = gpiod.line_request()
    config.consumer = "Blink"
    config.request_type = gpiod.line_request.DIRECTION_OUTPUT
    gpiod_pin.request(config)
    return gpiod_pin


def setUpdateStatus(gpiod_pin, busy):
    if busy is True:
        gpiod_pin.set_value(1)
    else:
        gpiod_pin.set_value(0)


def update():
    if not DEBUG:
        gpio_pin = initGPIO()
        setUpdateStatus(gpio_pin, True)
    
    logging.info('Weather information object setup START')
    wi = weatherInfomation()
    logging.info('Weather information object setup END')
    
    cv = Image.new("RGB", getCanvasSize(wi.inky_size), getDisplayColor(WHITE))
    
    logging.info('Prepare screen content START')
    drawWeather(wi, cv)
    logging.info('Prepare screen content END')

    cv.show()

    if not DEBUG:
        logging.info('Draw on screen START')
        _Inky = Inky_Impressions_57 if wi.inky_size == "57" else Inky_Impressions_73
        inky = _Inky()
        logging.info('Set Image START ...')
        inky.set_image(cv, saturation=saturation)
        logging.info('Set Image END ...')
        logging.info('Show Inky START ...') # long running
        inky.show()
        logging.info('Show Inky END ...')
        logging.info('Draw on screen END')

        setUpdateStatus(gpio_pin, False)


if __name__ == "__main__":
    update()
