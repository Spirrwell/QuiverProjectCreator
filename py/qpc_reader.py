# Reads QPC files and returns a list of QPCBlocks

# python 4 is chad
from __future__ import annotations

import os
from typing import List
from re import compile
from qpc_logging import warning, error, warning_no_line, verbose, verbose_color, print_color, Color


def posix_path(string: str) -> str:
    return string.replace("\\", "/")


COND_OPERATORS = compile('(\\(|\\)|\\|\\||\\&\\&|>=|<=|==|!=|>|<)')


class QPCBlock:
    def __init__(self, parent: QPCBlock, key: str, values: List[str] = None, condition: str = "", line_num: int = 0):
        self.parent: QPCBlock = parent
        self.items: List[QPCBlock] = []
        self.key: str = key
        self.values: List[str] = self._values_check(values)
        self.condition: str = condition
        self.line_num: int = line_num
    
    def __iter__(self):
        return self.items.__iter__()
    
    def __getitem__(self, index):
        return self.items[index]
    
    def extend(self, item):
        self.items.extend(item)
    
    def append(self, item):
        self.items.append(item)
    
    def remove(self, item):
        self.items.remove(item)
    
    def index(self, item):
        self.items.index(item)
    
    def to_string(self, quote_keys=False, quote_values=False, break_multi_value=False, break_on_key=False, depth=0):
        indent = "{0}".format(depth * '\t')
        index = self.parent.items.index(self)
        
        if quote_keys:
            string = "{0}\"{1}\"".format(indent, self.key)
        else:
            string = indent + self.key
        
        if break_on_key:
            key_indent = 0
        else:
            key_indent = len(self.key) - 1
        
        if self.values:
            for value_index, value in enumerate(self.values):
                if quote_values:
                    # we are adding quotes to this anyway, so just escape all existing quotes
                    formatted_value = value.replace("'", "\\'").replace('"', '\\"')
                else:
                    formatted_value = value.replace("'", "\\'")
                    if formatted_value:
                        if len(value) > 1:
                            # if we already have quotes at the ends of the the value, do not escape those quotes
                            formatted_value = formatted_value[0] + \
                                                  formatted_value[1:-1].replace('"', '\\"') + \
                                                  formatted_value[-1]
                        else:
                            # someone could do something weird with this and just have it be a single quote, right?
                            # that single quote would need to be escaped
                            formatted_value.replace('"', '\\"')
                            
                if quote_values:
                    string += " \"{0}\"".format(formatted_value)
                else:
                    string += " {0}".format(formatted_value)
                # untested
                if break_multi_value and value_index < len(self.values):
                    string += " \\\n{0}{1}".format(indent, " " * key_indent)
        
        if self.condition:
            string += " [" + add_spacing_to_condition(self.condition) + "]"
        
        if self.items:
            if 0 < index < len(self.parent.items):
                if not self.parent.items[index - 1].items:
                    string = "\n" + string
            
            string += "\n" + indent + "{\n"
            for item in self.items:
                string += item.to_string(quote_keys, quote_values, break_multi_value, break_on_key, depth + 1) + "\n"
            string += indent + "}"
            
            if index < len(self.parent.items) - 1:
                string += "\n"
        
        return string
    
    def get_value(self, index: int = 0) -> str:
        return self.values[index] if len(self.values) > index else ""
    
    def get_list(self) -> tuple:
        return (self.key, *self.values)  # need parenthesis for python versions older than 3.8
    
    def solve_condition(self, macros: dict):
        return solve_condition(self, self.condition, macros)
    
    def invalid_option(self, value: str, *valid_option_list):
        warning(self.get_file_info(), f"Invalid Option: {value}", "Valid Options:", *valid_option_list)
    
    def error(self, message):
        error(self.get_file_info(), message)
    
    def warning(self, message):
        warning(self.get_file_info(), message)
        
    def get_file_info(self) -> str:
        return f"File \"{self.get_file_path()}\" : Line {str(self.line_num)} : Key \"{self.key}\""
    
    def print_info(self):
        print(self.get_file_info() + " this should not be called anymore")
        
    @staticmethod
    def _values_check(values) -> List[str]:
        if type(values) == str:
            return [values]
        elif values is None:
            return []
        else:
            return values
        
    def move_item(self, item: QPCBlock):
        self.items.append(item)
        if item.parent:
            item.parent.remove(item)
        item.parent = self

    def add_item(self, key: str, values: List[str] = None, condition: str = "", line_num: int = 0) -> QPCBlock:
        values = self._values_check(values)
        sub_qpc = QPCBlock(self, key, values, condition, line_num=line_num)
        self.items.append(sub_qpc)
        return sub_qpc

    def add_item_index(self, index: int, key: str, values: List[str] = None, condition: str = "", line_num: int = 0) -> QPCBlock:
        values = self._values_check(values)
        sub_qpc = QPCBlock(self, key, values, condition, line_num=line_num)
        self.items.insert(index, sub_qpc)
        return sub_qpc

    def get_item(self, item_key) -> QPCBlock:
        for item in self.items:
            if item.key == item_key:
                return item
        return None

    def get_item_values(self, item_key) -> List[str]:
        for item in self.items:
            if item.key == item_key:
                return item.values
        return []

    def get_items(self, item_key) -> List[QPCBlock]:
        items: List[QPCBlock] = []
        for item in self.items:
            if item.key == item_key:
                items.append(item)
        return items

    def get_items_cond(self, macros: dict) -> List[QPCBlock]:
        items: List[QPCBlock] = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.append(item)
        return items

    def get_item_keys_condition(self, macros: dict) -> List[str]:
        items: List[str] = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.append(item.key)
        return items

    def get_item_values_condition(self, macros: dict, key: str = "") -> List[str]:
        items: List[str] = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                if not key or key == item.key:
                    items.extend(item.values)
        return items

    def get_item_list_condition(self, macros: dict) -> List[QPCBlock]:
        items = []
        for item in self.items:
            if solve_condition(self, item.condition, macros):
                items.extend([item.key, *item.values])
        return items

    def get_keys_in_items(self):
        return [value.key for value in self.items]

    def get_item_index(self, qpc_item: QPCBlock):
        try:
            return self.items.index(qpc_item)
        except IndexError:
            return None

    def get_root(self) -> QPCBlockRoot:
        return self.parent.get_root()

    def get_file_path(self) -> str:
        return self.get_root().file_path

    def get_file_name(self) -> str:
        return os.path.basename(self.get_root().file_path)


# tbh, this "base" class is pretty stupid and probably useless
# this should be like a "root" class
class QPCBlockRoot(QPCBlock):
    def __init__(self, file_path: str = ""):
        super().__init__(self, "", [])
        self.file_path = file_path
    
    def to_string(self, quote_keys=False, quote_values=False, break_multi_value=False, break_on_key=False, depth=0):
        final_string = ""
        for item in self.items:
            final_string += item.to_string(quote_keys, quote_values, break_multi_value, break_on_key, 0) + "\n"
        return final_string
    
    def get_root(self) -> QPCBlockRoot:
        return self


def replace_macros_condition(split_string: List[str], macros):
    for index, item_token in enumerate(split_string):
        flip_value = str(item_token).startswith("!")
        has_tokens = item_token[1 if flip_value else 0] == "$" and item_token.endswith("$")
        if has_tokens:
            item = item_token[2 if flip_value else 1:-1]
        else:
            item = item_token[1 if flip_value else 0:]
        
        if item in macros:
            if flip_value:
                try:
                    split_string[index] = str(int(not int(macros[item])))
                except ValueError:
                    split_string[index] = str(int(not macros[item]))
            else:
                split_string[index] = macros[item]
        
        elif flip_value:
            split_string[index] = "1"
        
        elif has_tokens:
            split_string[index] = "0"
    
    return split_string


def _print_solved_condition(split_string: list, result: int):
    pass
    # verbose_color(Color.BLUE, f"Solved Condition: \"[{' '.join(split_string)}]\" -> \"{result}\"")


def solve_condition(qpcblock: QPCBlock, condition: str, macros: dict) -> int:
    if not condition:
        return True
    
    solved_cond = condition
    # solve any sub conditionals first
    while "(" in solved_cond:
        sub_cond_line = (solved_cond.split('(')[1]).split(')')[0]
        sub_cond_value = solve_condition(qpcblock, sub_cond_line, macros)
        solved_cond = solved_cond.split('(', 1)[0] + str(sub_cond_value * 1) + solved_cond.split(')', 1)[1]
    
    split_string = COND_OPERATORS.split(solved_cond)
    
    solved_cond = replace_macros_condition(split_string.copy(), macros)
    
    if len(solved_cond) == 1:
        try:
            solved_cond[0] = int(solved_cond[0])
        except ValueError:
            _print_solved_condition(split_string, 1)
            return 1
    
    while len(solved_cond) > 1:
        try:
            solved_cond = _solve_single_condition(solved_cond)
        except Exception as F:
            qpcblock.error(f'Error Solving Condition: {str(F)}\n'
                           f'\tCondition: [{condition}] -> [{" ".join(solved_cond)}]\n')
            return 0

    _print_solved_condition(split_string, solved_cond[0])
    return solved_cond[0]


def _solve_single_condition(cond):
    index = 1
    result = 0
    # highest precedence order
    if "<" in cond:
        index = cond.index("<")
        if int(cond[index - 1]) < int(cond[index + 1]):
            result = 1
    
    elif "<=" in cond:
        index = cond.index("<=")
        if int(cond[index - 1]) <= int(cond[index + 1]):
            result = 1
    
    elif ">=" in cond:
        index = cond.index(">=")
        if int(cond[index - 1]) >= int(cond[index + 1]):
            result = 1
    
    elif ">" in cond:
        index = cond.index(">")
        if int(cond[index - 1]) > int(cond[index + 1]):
            result = 1
    
    # next in order of precedence, check equality
    # you can compare stings with these 2
    elif "==" in cond:
        index = cond.index("==")
        if str(cond[index - 1]) == str(cond[index + 1]):
            result = 1
    
    elif "!=" in cond:
        index = cond.index("!=")
        if str(cond[index - 1]) != str(cond[index + 1]):
            result = 1
    
    # and then, check for any &&'s
    elif "&&" in cond:
        index = cond.index("&&")
        if int(cond[index - 1]) > 0 and int(cond[index + 1]) > 0:
            result = 1
    
    # and finally, check for any ||'s
    elif "||" in cond:
        index = cond.index("||")
        if int(cond[index - 1]) > 0 or int(cond[index + 1]) > 0:
            result = 1
    
    cond[index] = result
    del cond[index + 1]
    del cond[index - 1]
    
    return cond


def add_spacing_to_condition(cond):
    cond = cond.strip(" ")
    
    if ">=" not in cond:
        cond = cond.replace(">", " > ")
    if "<=" not in cond:
        cond = cond.replace("<", " < ")
    
    for operator in ("<=", ">=", "==", "||", "&&"):
        cond = cond.replace(operator, ' ' + operator + ' ')
    
    return cond


def read_file(path: str, keep_quotes: bool = False, allow_escapes: bool = True, multiline_quotes: bool = False) -> QPCBlockRoot:
    path = posix_path(path)
    lexer = QPCLexer(path, keep_quotes, allow_escapes, multiline_quotes)
    qpc_file = QPCBlockRoot(path)
    path = posix_path(os.getcwd() + "/" + path)
    parse_recursive(lexer, qpc_file, path)
    return qpc_file


def parse_recursive(lexer, block, path):
    while lexer.char_num < lexer.file_len - 1:
        key, line_num = lexer.next_key()
        
        if not key:
            if lexer.next_symbol() == "}":
                return
            elif lexer.char_num >= lexer.file_len:
                if type(block) == QPCBlock:
                    block.warning("brackets do not close")
                return
            # print("WARNING: script is probably incorrect somewhere, no key specified, or a reader error")
            # block.print_info()
        
        # line_num = lexer.line_num
        values = lexer.next_value_list()
        condition = lexer.next_condition()
        
        sub_block = block.add_item(key, values, condition, line_num)
        
        next_symbol = lexer.next_symbol()
        if next_symbol == "{":
            parse_recursive(lexer, sub_block, path)
        elif next_symbol == "}":
            return


class QPCLexer:
    def __init__(self, path: str, keep_quotes: bool = False, allow_escapes: bool = True, multiline_quotes: bool = False):
        self.char_num = 0
        self.line_num = 1
        self.line_char = 0
        self.path = path
        self.keep_quotes = keep_quotes
        self.allow_escapes = allow_escapes
        self.multiline_quotes = multiline_quotes
        
        try:
            with open(path, mode="r", encoding="utf-8") as file:
                self.file = file.read()
        except UnicodeDecodeError:
            with open(path, mode="r", encoding="ansi") as file:
                self.file = file.read()
            
        self.file_len = len(self.file) - 1
        self.split_file = self.file.splitlines()
        
        self.chars_escape = {'\'', '"', '\\'}
        self.chars_comment = {'/', '*'}
        self.chars_item = {'{', '}'}
        self.chars_cond = {'[', ']'}
        self.chars_space = {' ', '\t'}
        self.chars_quote = {'"', '\''}

    def formatted_info(self) -> str:
        return f"File \"{self.path}\" : Line {str(self.line_num)} : Char {self.char_num}"
    
    def get_current_line(self) -> str:
        if -1 < self.line_num <= self.file_len:
            return self.split_file[self.line_num - 1]
        return ""
    
    @staticmethod
    def _make_arrow(index: int, length: int) -> str:
        arrow = "{0}^{1}".format(" " * (index - 1), "~" * length if length else "")
        return arrow

    def warning_range(self, index: int, length: int, *text):
        file_error = self._make_arrow(index, length)
        warning_no_line(self.formatted_info(), *text)
        print(self.get_current_line().replace("\t", " "))
        print_color(Color.GREEN, file_error)
        
    def next_line(self):
        self.line_num += 1
        self.line_char = 0
        
    def next_char(self, amount: int = 1):
        self.char_num += amount
        self.line_char += amount
    
    def next_value_list(self):
        start = self.line_char
        values = []
        current_value = ''
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                break
            
            if char in self.chars_space:
                if current_value:
                    if current_value != '\\':
                        values.append(current_value)
                        current_value = ''
                self.next_char()
                start = self.line_char
                continue
            
            if char in {'"', '\''}:
                if current_value and current_value != "\\":
                    self.warning_range(start, self.line_char - start,
                                       "Opening a quote inside a string, using quote only")
                values.append(self.read_quote(char))
                current_value = ""
                start = self.line_char
                continue
            
            # skip escape
            if char == '\\' and self.peek_char() in self.chars_escape:
                self.next_char(2)
                current_value += self.file[self.char_num]
                # char = self.file[self.char_num]
            
            elif char == '\n':
                if not current_value.endswith("\\"):
                    if current_value and not current_value.startswith('[') and not current_value.endswith(']'):
                        values.append(current_value)
                    break
                else:
                    self.next_line()
                    start = 0
            
            elif char == '/' and self.peek_char() in self.chars_comment:
                self.skip_comment()
                continue
            
            else:
                if self.file[self.char_num] in self.chars_cond:
                    break
                if current_value == '\\':
                    current_value = ''
                current_value += self.file[self.char_num]
            
            self.next_char()
        
        return values
    
    def peek_char(self):
        if self.char_num + 1 >= self.file_len:
            return None
        return self.file[self.char_num + 1]
    
    # used to be NextString, but i only used it for keys
    def next_key(self):
        string = ""
        line_num = 0
        skip_list = {' ', '\t', '\n'}
        
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                line_num = self.line_num
                break
            
            elif char in self.chars_space:
                if string:
                    line_num = self.line_num
                    break
            
            elif char in self.chars_quote:
                string = self.read_quote(char)
                line_num = self.line_num
                break
            
            # skip escape
            elif char == '\\' and self.peek_char() in self.chars_escape:
                self.next_char(2)
                string += self.file[self.char_num]
                # char = self.file[self.char_num]
            
            elif char in skip_list:
                if string:
                    line_num = self.line_num
                    break
                if char == '\n':
                    self.next_line()
            
            elif char == '/' and self.peek_char() in self.chars_comment:
                self.skip_comment()
                continue
            
            else:
                string += self.file[self.char_num]
                
            self.next_char()
            
        return string, line_num
    
    def next_symbol(self):
        while self.char_num <= self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                self.next_char()
                return char
            
            # skip escape
            elif char == '\\' and self.peek_char() in self.chars_escape:
                self.next_char(2)
            
            elif char == '/' and self.peek_char() in self.chars_comment:
                self.skip_comment()
                continue
            
            elif char == '\n':
                self.next_line()
            
            elif char not in self.chars_space:
                break
            
            self.next_char()
        
        return None
    
    def next_condition(self):
        condition = ''
        while self.char_num < self.file_len:
            char = self.file[self.char_num]
            
            if char in self.chars_item:
                break
            
            elif char == '[':
                self.next_char()
                continue
            
            elif char == ']':
                self.next_char()
                break
            
            elif char in self.chars_space:
                self.next_char()
                continue
            
            elif char == '\n':
                self.next_line()
                self.next_char()
                break
            
            elif char == '/' and self.peek_char() in self.chars_comment:
                self.skip_comment()
                continue
            
            else:
                condition += self.file[self.char_num]
            
            self.next_char()
        
        return condition
    
    def skip_comment(self):
        self.next_char()
        char = self.file[self.char_num]
        if char == '/':
            # keep going until \n
            while self.char_num < self.file_len:
                self.next_char()
                if self.file[self.char_num] == "\n":
                    break
        
        elif char == '*':
            while self.char_num < self.file_len:
                char = self.file[self.char_num]
                
                if char == '*' and self.peek_char() == '/':
                    self.next_char(2)
                    break
                
                if char == "\n":
                    self.next_line()
                
                self.next_char()
    
    def read_quote(self, quote_char):
        start = self.line_char
        
        if self.keep_quotes:
            quote = quote_char
        else:
            quote = ''
        
        while self.char_num < self.file_len:
            self.next_char()
            char = self.file[self.char_num]
            
            if char == '\\' and self.peek_char() in self.chars_escape and self.allow_escapes:
                quote += self.peek_char()
                self.next_char()
            elif char == quote_char:
                if self.keep_quotes:
                    quote += char
                break
            elif char == "\n" and not self.multiline_quotes:
                self.warning_range(start, self.line_char - start, "Quote does not end on line")
                break
            else:
                quote += char
        
        self.next_char()
        return quote
