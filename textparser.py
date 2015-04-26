# TextParser - An event-based text parser for Python.
# Copyright (C) 2015 Dario Giovannetti <dev@dariogiovannetti.net>
#
# This file is part of TextParser.
#
# TextParser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TextParser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with TextParser.  If not, see <http://www.gnu.org/licenses/>.

import bisect
import eventdispatcher


class TextParser:
    def __init__(self, text):
        # self.remainder_text stores the part of text that still has to be
        #  processed
        self.remainder_text = text
        self.eventdispatcher = eventdispatcher.EventDispatcher()
        self._update_mark_position = self._update_mark_position_continue
        # self.next_marks_revpos lists the next positions of the element
        #  start marks in the *reverse* order they seem to appear in
        #  self.remainder_text; the positions are however counted from the
        #  *end* of self.remainder_text, so they are in ascending order in
        #  the list
        self.next_marks_revpos = []
        # self.next_marks lists the matches associated to the same-index
        #  position in self.next_marks_revpos
        self.next_marks = []
        # self.next_events lists the events associated to the same-index
        #  position in self.next_marks_revpos
        self.next_events = []

    def _update_mark_position(self, Event):
        # This method is defined dynamically with self._update_mark_position_*
        #  methods
        pass

    def _update_mark_position_continue(self, Event):
        # This method must accept the same arguments as the other
        #  self._update_mark_position_* methods
        # This method assumes that Event is not stored in the self.next_* lists
        #  yet/anymore
        mark = Event.MARK.search(self.remainder_text)
        if mark is None:
            # Use unbind_all because only one handler was supposed to handle
            #  the text event
            self.eventdispatcher.unbind_all(Event)
        else:
            revpos = len(self.remainder_text) - mark.start()
            revposindex = bisect.bisect_left(self.next_marks_revpos, revpos)
            self.next_marks_revpos.insert(revposindex, revpos)
            self.next_marks.insert(revposindex, mark)
            self.next_events.insert(revposindex, Event)

    def _update_mark_position_terminate(self, Event):
        # This method must accept the same arguments as the other
        #  self._update_mark_position_* methods
        for Event in self.next_events:
            self.eventdispatcher.unbind_all(Event)
        self.next_marks_revpos.clear()
        self.next_marks.clear()
        self.next_events.clear()

    def reset_bindings(self, bindings):
        newbindings = set(bindings.keys()) - set(self.next_events)
        delbindings = set(self.next_events) - set(bindings.keys())
        for Event in bindings:
            handler = bindings[Event]
            # Use bind_one because only one handler must handle a text event
            self.eventdispatcher.bind_one(Event, handler)
        for Event in delbindings:
            # Use unbind_all because only one handler was supposed to handle
            #  the text event
            self.eventdispatcher.unbind_all(Event)
            index = self.next_events.index(Event)
            del self.next_marks_revpos[index]
            del self.next_marks[index]
            del self.next_events[index]
        for Event in newbindings:
            # Run self._update_mark_position_continue *after* binding the
            #  handlers, so that self._update_mark_position_continue can unbind
            #  it if there are no matches
            self._update_mark_position(Event)

    def parse(self):
        while True:
            try:
                # Do not pop values here, see comment below
                revpos = self.next_marks_revpos[-1]
            except IndexError:
                break
            # Do not pop values here, see comment below
            mark = self.next_marks[-1]
            # Remember that mark was, in general, found with a different
            #  self.remainder_text, so its absolute start and end values cannot
            #  be trusted; the difference (the length of the match), however,
            #  is still valid
            startpos = revpos * -1
            endpos = startpos - mark.start() + mark.end()
            # Do not pop the Event here, because for example the handler might
            #  call self.reset_bindings, which needs the Event to be in the
            #  list
            Event = self.next_events[-1]
            processed_text = self.remainder_text[:startpos]
            self.remainder_text = self.remainder_text[endpos:] \
                                  if endpos < 0 else ''
            # It's important that the Event is still in self.next_events while
            #  the event is handled, see also comment above
            self.eventdispatcher.fire(Event, Event(mark, processed_text))
            # The event handler might have called self.reset_bindings and
            #  unbound this very Event
            if self.eventdispatcher.has_handlers(Event):
                del self.next_marks_revpos[-1]
                del self.next_marks[-1]
                del self.next_events[-1]
                self._update_mark_position(Event)

        self.eventdispatcher.fire(RemainderEvent,
                                  RemainderEvent(self.remainder_text))
        return self.remainder_text

    def terminate(self):
        self._update_mark_position = self._update_mark_position_terminate


class MarkEvent:
    MARK = None

    def __init__(self, mark, processed_text):
        self.mark = mark
        self.processed_text = processed_text


class RemainderEvent:
    def __init__(self, remainder_text):
        self.remainder_text = remainder_text
