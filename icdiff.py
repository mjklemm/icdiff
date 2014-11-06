""" icdiff.py

Author: Jeff Kaufman, derived from difflib.HtmlDiff

License: This code is usable under the same open terms as the rest of
         python.  See: http://www.python.org/psf/license/

"""

import os
import sys
import difflib
import optparse
import re

class ConsoleDiff(object):
    """Console colored side by side comparison with change highlights.

    Based on difflib.HtmlDiff

    This class can be used to create a text-mode table showing a side
    by side, line by line comparison of text with inter-line and
    intra-line change highlights in ansi color escape sequences as
    read by xterm.  The table can be generated in either full or
    contextual difference mode.

    To generate the table, call make_table.

    Usage is the almost the same as HtmlDiff except only make_table is
    implemented and the file can be invoked on the command line.
    Run::

      python icdiff.py --help

    for command line usage information.

    """

    def __init__(self,tabsize=8,wrapcolumn=None,linejunk=None,
                 charjunk=difflib.IS_CHARACTER_JUNK, cols=80,
                 line_numbers=False,
                 show_all_spaces=False,
                 highlight=False):
        """ConsoleDiff instance initializer

        Arguments:
        tabsize -- tab stop spacing, defaults to 8.
        wrapcolumn -- column number where lines are broken and wrapped,
            defaults to None where lines are not wrapped.
        linejunk,charjunk -- keyword arguments passed into ndiff() (used by
            ConsoleDiff() to generate the side by side differences).  See
            ndiff() documentation for argument default values and descriptions.
        """

        self._tabsize = tabsize
        self.line_numbers = line_numbers
        self.cols = cols
        self.show_all_spaces = show_all_spaces
        self.highlight=highlight

        if wrapcolumn is None:
            if not line_numbers:
                wrapcolumn = self.cols/2-2
            else:
                wrapcolumn = self.cols/2-10
        
        self._wrapcolumn = wrapcolumn
        self._linejunk = linejunk
        self._charjunk = charjunk


    def _tab_newline_replace(self,fromlines,tolines):
        """Returns from/to line lists with tabs expanded and newlines removed.

        Instead of tab characters being replaced by the number of spaces
        needed to fill in to the next tab stop, this function will fill
        the space with tab characters.  This is done so that the difference
        algorithms can identify changes in a file when tabs are replaced by
        spaces and vice versa.  At the end of the table generation, the tab
        characters will be replaced with a space.
        """
        def expand_tabs(line):
            # hide real spaces
            line = line.replace(' ','\0')
            # expand tabs into spaces
            line = line.expandtabs(self._tabsize)
            # relace spaces from expanded tabs back into tab characters
            # (we'll replace them with markup after we do differencing)
            line = line.replace(' ','\t')
            return line.replace('\0',' ').rstrip('\n')
        fromlines = [expand_tabs(line) for line in fromlines]
        tolines = [expand_tabs(line) for line in tolines]
        return fromlines,tolines

    def _split_line(self,data_list,line_num,text):
        """Builds list of text lines by splitting text lines at wrap point

        This function will determine if the input text line needs to be
        wrapped (split) into separate lines.  If so, the first wrap point
        will be determined and the first line appended to the output
        text line list.  This function is used recursively to handle
        the second part of the split line to further split it.
        """
        # if blank line or context separator, just add it to the output list
        if not line_num:
            data_list.append((line_num,text))
            return

        # if line text doesn't need wrapping, just add it to the output list
        size = len(text)
        max = self._wrapcolumn
        if (size <= max) or ((size -(text.count('\0')*3)) <= max):
            data_list.append((line_num,text))
            return

        # scan text looking for the wrap point, keeping track if the wrap
        # point is inside markers
        i = 0
        n = 0
        mark = ''
        while n < max and i < size:
            if text[i] == '\0':
                i += 1
                mark = text[i]
                i += 1
            elif text[i] == '\1':
                i += 1
                mark = ''
            else:
                i += 1
                n += 1

        # wrap point is inside text, break it up into separate lines
        line1 = text[:i]
        line2 = text[i:]

        # if wrap point is inside markers, place end marker at end of first
        # line and start marker at beginning of second line because each
        # line will have its own table tag markup around it.
        if mark:
            line1 = line1 + '\1'
            line2 = '\0' + mark + line2

        # tack on first line onto the output list
        data_list.append((line_num,line1))

        # use this routine again to wrap the remaining text
        self._split_line(data_list,'>',line2)

    def _line_wrapper(self,diffs):
        """Returns iterator that splits (wraps) mdiff text lines"""

        # pull from/to data and flags from mdiff iterator
        for fromdata,todata,flag in diffs:
            # check for context separators and pass them through
            if flag is None:
                yield fromdata,todata,flag
                continue
            (fromline,fromtext),(toline,totext) = fromdata,todata
            # for each from/to line split it at the wrap column to form
            # list of text lines.
            fromlist,tolist = [],[]
            self._split_line(fromlist,fromline,fromtext)
            self._split_line(tolist,toline,totext)
            # yield from/to line in pairs inserting blank lines as
            # necessary when one side has more wrapped lines
            while fromlist or tolist:
                if fromlist:
                    fromdata = fromlist.pop(0)
                else:
                    fromdata = ('',' ')
                if tolist:
                    todata = tolist.pop(0)
                else:
                    todata = ('',' ')
                yield fromdata,todata,flag

    def _collect_lines(self,diffs):
        """Collects mdiff output into separate lists

        Before storing the mdiff from/to data into a list, it is converted
        into a single line of text with console markup.
        """

        fromlist,tolist,flaglist = [],[],[]
        # pull from/to data and flags from mdiff style iterator
        for fromdata,todata,flag in diffs:
            try:
                # store HTML markup of the lines into the lists
                fromlist.append(self._format_line(0,flag,*fromdata))
                tolist.append(self._format_line(1,flag,*todata))
            except TypeError:
                # exceptions occur for lines where context separators go
                fromlist.append(None)
                tolist.append(None)
            flaglist.append(flag)
        return fromlist,tolist,flaglist

    def _format_line(self,side,flag,linenum,text):
        """Returns HTML markup of "from" / "to" text lines

        side -- 0 or 1 indicating "from" or "to" text
        flag -- indicates if difference on line
        linenum -- line number (used for line number column)
        text -- line text to be marked up
        """
        try:
            id = '%d' % linenum
        except TypeError:
            # handle blank lines where linenum is '>' or ''
            id = ''

        text = text.rstrip()
            
        if not self.line_numbers:
            return text
        return '%s %s' % (self._rpad(id, 8), text)

    def _real_len(self, s):
        l = 0
        in_esc = False
        prev = ' '
        for c in s.replace('\0+',"").replace('\0-',"").replace('\0^',"").replace('\1',"").replace('\t',' '):
            if in_esc:
                if c == "m":
                    in_esc = False
            else:
                if c == "[" and prev == "\033":
                    in_esc = True
                    l -= 1 # we counted prev when we shouldn't have
                else:
                    l += 1
            prev = c

        #print "len '%s' is %d." % (s, l) 
        return l                
            
        
    def _rpad(self, s, field_width):
        return self._pad(s, field_width) + s

    def _pad(self, s, field_width):
        return " "*(field_width-self._real_len(s))

    def _lpad(self, s, field_width):
        target = s + self._pad(s, field_width)
        #if self._real_len(target) != field_width:
        #    print "Warning: bad line %r is not of length %d" % (target, field_width)
        return target

    def _convert_flags(self,fromlist,tolist,flaglist,context,numlines):
        """Makes list of "next" links"""

        # all anchor names will be generated using the unique "to" prefix

        # process change flags, generating middle column of next anchors/links
        next_id = ['']*len(flaglist)
        next_href = ['']*len(flaglist)
        num_chg, in_change = 0, False
        last = 0
        toprefix = ''
        for i,flag in enumerate(flaglist):
            if flag:
                if not in_change:
                    in_change = True
                    last = i
                    # at the beginning of a change, drop an anchor a few lines
                    # (the context lines) before the change for the previous
                    # link
                    i = max([0,i-numlines])
                    next_id[i] = ' id="difflib_chg_%s_%d"' % (toprefix,num_chg)
                    # at the beginning of a change, drop a link to the next
                    # change
                    num_chg += 1
                    next_href[last] = '<a href="#difflib_chg_%s_%d">n</a>' % (
                         toprefix,num_chg)
            else:
                in_change = False
        # check for cases where there is no content to avoid exceptions
        if not flaglist:
            flaglist = [False]
            next_id = ['']
            next_href = ['']
            last = 0
            if context:
                fromlist = ['No Differences Found']
                tolist = fromlist
            else:
                fromlist = tolist = ['Empty File']
        # if not a change on first line, drop a link
        if not flaglist[0]:
            next_href[0] = '<a href="#difflib_chg_%s_0">f</a>' % toprefix
        # redo the last link to link to the top
        next_href[last] = '<a href="#difflib_chg_%s_top">t</a>' % (toprefix)

        return fromlist,tolist,flaglist,next_href,next_id

    def make_table(self,fromlines,tolines,fromdesc='',todesc='',context=False,
                   numlines=5):
        """Returns table of side by side comparison with change highlights

        Arguments:
        fromlines -- list of "from" lines
        tolines -- list of "to" lines
        fromdesc -- "from" file column header string
        todesc -- "to" file column header string
        context -- set to True for contextual differences (defaults to False
            which shows full differences).
        numlines -- number of context lines.  When context is set True,
            controls number of lines displayed before and after the change.
            When context is False, controls the number of lines to place
            the "next" link anchors before the next change (so click of
            "next" link jumps to just before the change).
        """

        # change tabs to spaces before it gets more difficult after we insert
        # markkup
        fromlines,tolines = self._tab_newline_replace(fromlines,tolines)

        # create diffs iterator which generates side by side from/to data
        if context:
            context_lines = numlines
        else:
            context_lines = None
        diffs = difflib._mdiff(fromlines,tolines,context_lines,linejunk=self._linejunk,
                               charjunk=self._charjunk)


        # set up iterator to wrap lines that exceed desired width
        if self._wrapcolumn:
            diffs = self._line_wrapper(diffs)

        # collect up from/to lines and flags into lists (also format the lines)
        fromlist,tolist,flaglist = self._collect_lines(diffs)

        # process change flags, generating middle column of next anchors/links
        fromlist,tolist,flaglist,next_href,next_id = self._convert_flags(
            fromlist,tolist,flaglist,context,numlines)

        s = []

        if fromdesc or todesc:
            s.append((fromdesc, todesc))

        for i in range(len(flaglist)):
            if flaglist[i] is None:
                # mdiff yields None on separator lines skip the bogus ones
                # generated for the first line
                if i > 0:
                    s.append( ('---', '---') )
            else:
                s.append( (fromlist[i], tolist[i]) )

        table_lines = []
        for sides in s:
            line = []
            for side in sides:
                line.append(self._lpad(side, self.cols/2-1))
            table_lines.append(" ".join(line))

        table_line_string="\n".join(table_lines)

        colorized_table_line_string = self.colorize(table_line_string)

        return colorized_table_line_string

    def colorize(self, s):

        import time
        initial_time = time.time()

        def background(color):
            return color.replace("\033[1;", "\033[7;")

        C_ADD = '\033[1;31m'
        C_SUB = '\033[1;32m'
        C_CHG = '\033[1;33m'

        if self.highlight:
            C_ADD, C_SUB, C_CHG = background(C_ADD), background(C_SUB), background(C_CHG)
        
        C_NONE = '\033[m'
        colors = (C_ADD, C_SUB, C_CHG, C_NONE)

        s = s.replace('\0+', C_ADD).replace('\0-', C_SUB).replace('\0^', C_CHG).replace('\1', C_NONE).replace('\t',' ')

        if self.highlight:
            return s

        if not self.show_all_spaces:
            return re.sub("\033\\[1;3([123])m(\\s+)(\033\\[)", "\033[7;3\\1m\\2\\3", s)
        
        def will_see_coloredspace(i, s):
            while i < len(s) and s[i].isspace():
                i += 1
            if i < len(s) and s[i] == '\033':
                return False
            return True

        n_s = []
        in_color = False
        seen_coloredspace = False
        for i, c in enumerate(s):
            if len(n_s) > 6 and n_s[-1] == "m":
                ns_end = "".join(n_s[-7:])
                for color in colors:
                    if ns_end.endswith(color):
                        if color != in_color:
                            seen_coloredspace = False
                        in_color = color
                if ns_end.endswith(C_NONE):
                    in_color = False
                     
            if c.isspace() and in_color and (self.show_all_spaces or not (seen_coloredspace or will_see_coloredspace(i, s))):
                n_s.extend([C_NONE, background(in_color), c, C_NONE, in_color])
            else:
                if in_color:
                    seen_coloredspace = True
                n_s.append(c)

        joined = "".join(n_s)
        
        return joined
            
if __name__ == "__main__":

    parser = optparse.OptionParser(usage="usage: %prog [options] left_file right_file",
                                   description="Show differences between files in a two column view.")
    parser.add_option("--cols", default=None,
                      help="specify the width of the screen. Autodetection is Linux only")
    parser.add_option("--context", default=False,
                      action="store_true",
                      help="print only differences with some context")
    parser.add_option("--numlines", default=5,
                      help="how many lines of context to print; only meaningful with --context")
    parser.add_option("--line-numbers", default=False,
                      action="store_true",
                      help="generate output with line numbers")
    parser.add_option("--head", default=0,
                      help="consider only the first N lines of each file")
    parser.add_option("--highlight", default=False,
                      action="store_true",
                      help="color by changing the background color instead of the foreground color.  Very fast, ugly, displays all changes")
    parser.add_option("--show-all-spaces", default=False,
                      action="store_true",
                      help="color all non-matching whitespace including that which is not needed for drawing the eye to changes.  Slow, ugly, displays all changes")
    parser.add_option("--print-headers", default=False,
                      action="store_true",
                      help="label the left and right sides with their file names")
                      

    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        sys.exit()
        
    a, b = args

    if not options.cols:
        def ioctl_GWINSZ(fd):
            try:
                import fcntl, termios, struct, os
                cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
            except Exception:
                return None
            return cr
        cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
        if cr:
            options.cols = cr[1]
        else:
            options.cols = 80

    headers = a, b
    if not options.print_headers:
        headers = None, None

    head = int(options.head)
    lines_a = open(a, "U").readlines()
    lines_b = open(b, "U").readlines()

    if head != 0:
        lines_a = lines_a[:head]
        lines_b = lines_b[:head]
        
    print ConsoleDiff(cols=int(options.cols),
                      show_all_spaces=options.show_all_spaces,
                      highlight=options.highlight,
                      line_numbers=options.line_numbers).make_table(
        lines_a, lines_b, headers[0], headers[1], context=options.context, numlines=int(options.numlines))