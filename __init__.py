# Copyright 2017, Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import tzlocal
from astral import Astral
from pytz import timezone
import time

from adapt.intent import IntentBuilder
import mycroft.audio
from mycroft.skills.core import MycroftSkill, intent_handler
# from mycroft.util.format import nice_time
from mycroft.util.time import now_local
from mycroft.util.format import pronounce_number, nice_time
from mycroft.util.lang.format_de import nice_time_de, pronounce_ordinal_de
from ummalqura.hijri_date import HijriDate
from mycroft.util.time import now_local


# TODO: This is temporary until nice_time() gets fixed in mycroft-core's
# next release

def serialize(dt):
    return dt.strftime('%Y%d%m-%H%M%S-%z')



#Custom nice_date function for the datetime skill (different from the one in the fromat_ar)
def nice_date(dt, lang, now):

        days = {
    7: 'الأحد',
    1: 'الاثنين',
    2: 'الثلاثاء',
    3: 'الأربعاء',
    4: 'الخميس',
    5: 'الجمعة',
    6: 'السبت'
   }

        months = ['جانيوري', 'فبراير', 'مارس', 'أبريل', 'ماي', 'جون','جولاي', 'أوقست', 'سبتمبر', 'أكتوبر', 'نوفمبر','ديسمبر']
        year = str(dt.year)[2:]
        if now:

            tomorrow = now + datetime.timedelta(days=1)
            yesterday = now - datetime.timedelta(days=1)
                
            return days[dt.weekday()+1] + " "+ pronounce_number(dt.day, lang) + " " +months[dt.month-1] + " ألفين و" + pronounce_number(int(year), lang)


class TimeSkill(MycroftSkill):

    def __init__(self):
        super(TimeSkill, self).__init__("TimeSkill")
        self.astral = Astral()
        self.displayed_time = None
        self.display_tz = None
        self.answering_query = False

    def initialize(self):
        # Start a callback that repeats every 10 seconds
        # TODO: Add mechanism to only start timer when UI setting
        #       is checked, but this requires a notifier for settings
        #       updates from the web.
        now = datetime.datetime.now()
        callback_time = (datetime.datetime(now.year, now.month, now.day,
                                           now.hour, now.minute) +
                         datetime.timedelta(seconds=60))
        self.schedule_repeating_event(self.update_display, callback_time, 10)

    @property
    def use_24hour(self):
        return self.config_core.get('time_format') == 'full'

    def get_timezone(self, locale):
        try:
            # This handles common city names, like "Dallas" or "Paris"
            return timezone(self.astral[locale].timezone)
        except:
            try:
                # This handles codes like "America/Los_Angeles"
                return timezone(locale)
            except:
                return None

    def get_local_datetime(self, location):
        nowUTC = datetime.datetime.now(timezone('UTC'))
        
        if self.display_tz:
            tz = self.display_tz
        else:
            tz = self.get_timezone(self.location_timezone)

        if location:
            tz = self.get_timezone(location)
        if not tz:
            self.speak_dialog("time.tz.not.found", {"location": location})
            return None

        return nowUTC.astimezone(tz)

    def get_display_time(self, location=None):
        # Get a formatted digital clock time based on the user preferences
        dt = self.get_local_datetime(location)
        if not dt:
            return

        return nice_time(dt, self.lang, speech=False,
                         use_24hour=self.use_24hour)

    def get_spoken_time(self, location=None):
        # Get a formatted spoken time based on the user preferences
        dt = self.get_local_datetime(location)
        if not dt:
            return

        return nice_time(dt, self.lang, speech=True,
                         use_24hour=False)

    def display(self, display_time):
        # Map characters to the display encoding for a Mark 1
        # (4x8 except colon, which is 2x8)
        code_dict = {
            ':': 'CIICAA',
            '0': 'EIMHEEMHAA',
            '1': 'EIIEMHAEAA',
            '2': 'EIEHEFMFAA',
            '3': 'EIEFEFMHAA',
            '4': 'EIMBABMHAA',
            '5': 'EIMFEFEHAA',
            '6': 'EIMHEFEHAA',
            '7': 'EIEAEAMHAA',
            '8': 'EIMHEFMHAA',
            '9': 'EIMBEBMHAA',
        }


        # clear screen (draw two blank sections, numbers cover rest)
        if len(display_time) == 4:
            # for 4-character times, 9x8 blank
            self.enclosure.mouth_display(img_code="JIAAAAAAAAAAAAAAAAAA",
                                         refresh=False)
            self.enclosure.mouth_display(img_code="JIAAAAAAAAAAAAAAAAAA",
                                         x=22, refresh=False)
        else:
            # for 5-character times, 7x8 blank
            self.enclosure.mouth_display(img_code="HIAAAAAAAAAAAAAA",
                                         refresh=False)
            self.enclosure.mouth_display(img_code="HIAAAAAAAAAAAAAA",
                                         x=24, refresh=False)

        # draw the time, centered on display
        xoffset = (32 - (4*(len(display_time))-2)) / 2
        for c in display_time:
            if c in code_dict:
                self.enclosure.mouth_display(img_code=code_dict[c],
                                             x=xoffset, refresh=False)
                if c == ":":
                    xoffset += 2  # colon is 1 pixels + a space
                else:
                    xoffset += 4  # digits are 3 pixels + a space

    def _is_display_idle(self):
        # check if the display is being used by another skill right now
        # or _get_active() == "TimeSkill"
        return self.enclosure.display_manager.get_active() == ''

    def update_display(self, force=False):
        # Don't show idle time when answering a query to prevent
        # overwriting the displayed value.
        if self.answering_query:
            return

        if self.settings.get("show_time", False):
            # user requested display of time while idle
            if (force is True) or self._is_display_idle():
                current_time = self.get_display_time()
                if self.displayed_time != current_time:
                    self.displayed_time = current_time
                    self.display(current_time)
                    # return mouth to 'idle'
                    self.enclosure.display_manager.remove_active()
            else:
                self.displayed_time = None  # another skill is using display
        else:
            # time display is not wanted
            if self.displayed_time:
                if self._is_display_idle():
                    # erase the existing displayed time
                    self.enclosure.mouth_reset()
                    # return mouth to 'idle'
                    self.enclosure.display_manager.remove_active()
                self.displayed_time = None

    @intent_handler(IntentBuilder("").require("Query").require("Time").
                    optionally("Location"))
    def handle_query_time(self, message):
        location = message.data.get("Location")
        current_time = self.get_spoken_time(location)
        if not current_time:
            return

        # speak it
        self.speak_dialog("time.current", {"time": current_time})

        # and briefly show the time
        self.answering_query = True
        self.enclosure.deactivate_mouth_events()
        self.display(self.get_display_time(location))
        time.sleep(5)
        mycroft.audio.wait_while_speaking()
        self.enclosure.mouth_reset()
        self.enclosure.activate_mouth_events()
        self.answering_query = False
        self.displayed_time = None

    @intent_handler(IntentBuilder("").require("Display").require("Time").
                    optionally("Location"))
    def handle_show_time(self, message):
        self.display_tz = None
        location = message.data.get("Location")
        if location:
            tz = self.get_timezone(location)
            if not tz:
                self.speak_dialog("time.tz.not.found", {"location": location})
                return
            else:
                self.display_tz = tz

        # show time immediately
        self.settings["show_time"] = True
        self.update_display(True)

    @intent_handler(IntentBuilder("").require("Query").require("Date").
                    optionally("Location"))
    def handle_query_date(self, message):
        local_date = self.get_local_datetime(message.data.get("Location"))
        if not local_date:
            return

        # Get the current date
           
        lang_lower = str(self.lang).lower()

        if lang_lower.startswith("ar"):
            speak = nice_date(local_date, self.lang, now=now_local())


        if self.config_core.get('date_format') == 'MDY':
            show = local_date.strftime("%-m/%-d/%Y")
        else:
            show = nice_date(local_date)


       

        # speak it
        self.speak_dialog("date", {"date": speak})


        # and briefly show the time
        self.answering_query = True
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(show)
        time.sleep(10)
        mycroft.audio.wait_while_speaking()
        self.enclosure.mouth_reset()
        self.enclosure.activate_mouth_events()
        self.answering_query = False
        self.displayed_time = None


def create_skill():
    return TimeSkill()
