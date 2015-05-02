# TextParser - An event-based, single-iteration text parser for Python.
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
        # self.next_marks_match lists the matches associated to the same-index
        #  position in self.next_marks_revpos
        self.next_marks_match = []
        # self.next_marks_re lists the regular expression associated to the
        #  same-index position in self.next_marks_revpos
        self.next_marks_re = []

    def _update_mark_position(self, regex):
        # This method is defined dynamically with self._update_mark_position_*
        #  methods
        pass

    def _update_mark_position_continue(self, regex):
        # This method must accept the same arguments as the other
        #  self._update_mark_position_* methods
        # This method assumes that regex is not stored in the self.next_marks_*
        #  lists yet/anymore
        mark = regex.search(self.remainder_text)
        if mark is None:
            # Use unbind_all because only one handler was supposed to handle
            #  the text event
            self.eventdispatcher.unbind_all(regex)
        else:
            revpos = len(self.remainder_text) - mark.start()
            revposindex = bisect.bisect_left(self.next_marks_revpos, revpos)
            self.next_marks_revpos.insert(revposindex, revpos)
            self.next_marks_match.insert(revposindex, mark)
            self.next_marks_re.insert(revposindex, regex)

    def _update_mark_position_terminate(self, regex):
        # This method must accept the same arguments as the other
        #  self._update_mark_position_* methods
        for regex in self.next_marks_re:
            self.eventdispatcher.unbind_all(regex)
        self.next_marks_revpos.clear()
        self.next_marks_match.clear()
        self.next_marks_re.clear()

    def reset_bindings(self, bindings):
        newbindings = set(bindings.keys()) - set(self.next_marks_re)
        delbindings = set(self.next_marks_re) - set(bindings.keys())
        for regex in bindings:
            handler = bindings[regex]
            # Use bind_one because only one handler must handle a text event
            self.eventdispatcher.bind_one(regex, handler)
        for regex in delbindings:
            # Use unbind_all because only one handler was supposed to handle
            #  the text event
            self.eventdispatcher.unbind_all(regex)
            index = self.next_marks_re.index(regex)
            del self.next_marks_revpos[index]
            del self.next_marks_match[index]
            del self.next_marks_re[index]
        for regex in newbindings:
            # Run self._update_mark_position_continue *after* binding the
            #  handlers, so that self._update_mark_position_continue can unbind
            #  it if there are no matches
            self._update_mark_position(regex)

    def prepend_text_and_reset_bindings(self, text, bindings):
        self.remainder_text = ''.join((text, self.remainder_text))
        self.reset_bindings(bindings)

    def bind_to_parse_end(self, handler):
        self.eventdispatcher.bind_one(ParseEndEvent, handler)

    def parse(self):
        while True:
            try:
                # Do not pop values here, see comment below
                revpos = self.next_marks_revpos[-1]
            except IndexError:
                break
            # Do not pop values here, see comment below
            mark = self.next_marks_match[-1]
            # Remember that mark was, in general, found with a different
            #  self.remainder_text, so its absolute start and end values cannot
            #  be trusted; the difference (the length of the match), however,
            #  is still valid
            startpos = revpos * -1
            endpos = startpos - mark.start() + mark.end()
            # Do not pop the regex here, because for example the handler might
            #  call self.reset_bindings, which needs the regex to be in the
            #  list
            regex = self.next_marks_re[-1]
            parsed_text = self.remainder_text[:startpos]
            self.remainder_text = self.remainder_text[endpos:] \
                                  if endpos < 0 else ''
            # It's important that the regex is still in self.next_marks_re
            #  while the event is handled, see also comment above
            self.eventdispatcher.fire(regex, MarkEvent(mark, parsed_text))
            # The event handler might have called self.reset_bindings and
            #  unbound this very regex's event
            if self.eventdispatcher.has_handlers(regex):
                del self.next_marks_revpos[-1]
                del self.next_marks_match[-1]
                del self.next_marks_re[-1]
                self._update_mark_position(regex)

        self.eventdispatcher.fire(ParseEndEvent,
                                  ParseEndEvent(self.remainder_text))
        return self.remainder_text

    def terminate(self):
        self._update_mark_position = self._update_mark_position_terminate


class MarkEvent:
    def __init__(self, mark, parsed_text):
        self.mark = mark
        self.parsed_text = parsed_text


class ParseEndEvent:
    def __init__(self, remainder_text):
        self.remainder_text = remainder_text
