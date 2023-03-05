from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver

from graphviz import Digraph
import re
import os

options = Options()
options.headless = True # don't use a GUI (necessary on a VM)
service = Service(executable_path="chromium.chromedriver")
b = webdriver.Chrome(options=options, service=service)


number3_pattern = r"\d{3}"
white_space_pattern = r'\s{2,}'
parenthesis_pattern = r"\([^()]*\)"
parenthesis_and_pattern = r"\([^)]*and[^)]*\)"
digit3_capital_pattern = r"([A-Z]\s*\w*\s*[A-Z]|[0-9]{3})"
name_element_pattern = r'\b[A-Z][A-Z/\s]*[A-Z]\b|[0-9]{3}'

class Course:
    def __init__(self, name, number):
        self.name = name
        self.number = number
        # contains all courses, regardless of 'and' and 'or'.
        self.requisite = set()
        # reflects 'and' and 'or'. tuple = 'and', list = 'or'.
        # each chunk separated with 'and' is list, meaning that its components are related 'or'.
        # but it is one of components of self.combination, meaning that each list should be fulfilled.
        # update: cannot deal with tuple... it's contradicting, but it should be implemented to be a list. very tragic.
        self.combination = []
        
# number of target in origianl should match the length of substitution_list

def replace_with_list(original, substitution_list, target="TO_BE_SUBSTITUTED",):
    index = 0
    while original.find(target) != -1:
        original = original.replace(target, substitution_list[index], 1)
        index += 1
    return original

#within requisite statement, reove codes for link.

def remove_link(text):
    if text.find("<a href=") != -1:
        course = re.findall("title=(.*?)class", text)
        for i in range(len(course)):
            course[i] = course[i].replace("&nbsp;", " ").replace('"', "")
        substituted = re.sub("<a href(.*?)<\\/a>", "TO_BE_SUBSTITUTED", text)
        i = 0
        while substituted.find("TO_BE_SUBSTITUTED") != -1:
            substituted = substituted.replace("TO_BE_SUBSTITUTED", course[i], 1)
            i += 1
        return substituted
    else:
        return text
    
# function that takes list of course subject and number and generates full course names using them.

def course_generator(text):
    subject = ''
    generated = False
    course_list = []
    for piece in text:
        
        # check whether the piece is nubmer or letter. 
        # if number, concatenate it to subject
        if re.match(number3_pattern, piece):
            course_list.append(subject + " " + piece)
            generated = True
        else:
            # if first letter, that's your subject.
            if subject == '' or generated == True:
                subject = piece
            # if not first letter, concatenate it with /, as it's multi-subject course.
            else:
                subject = subject + "/" + piece
                
    return course_list

# generate graph using course name to search in the course dictionary.
# recursively call itself in requisite courses to expand the graph.

def graph_generator(course_name, course_dict, graph, spread = set()):
    
    if course_name not in course_dict.keys() or course_name in spread:
        return
    
    # prevent infinite recursion.
    spread.add(course_name)
    requisities = course_dict[course_name].requisite 
    for requisite in requisities:

        graph.edge(course_name, requisite)
        graph_generator(requisite, course_dict, graph, spread)

# remove all words that doesn't contain 3 numbers.

def num3(text, divider, join=True):

    text = text.split(divider)
    for i in range(len(text)):
        if len(re.findall(number3_pattern, text[i])) == 0:
            text[i] = ""
    if join == True:
        return ''.join(text)
    else:
        return text
    
# course name, course number, and course class instance.

def course_name_number_class(b, course_name_list, course_number_list, course_dict):
    

    elements = b.find_elements(By.CLASS_NAME, "courseblocktitle.noindent")
    for element in elements:
        rm_front = element.get_attribute("innerHTML").split('class="courseblockcode">')[1]
        course_number = rm_front.replace("&nbsp;", " ").split("</span> —")[0]
        course_number = re.sub(white_space_pattern, " ", course_number).strip()
        course_name = rm_front.split("</span> —")[1][:-9]
        course_name_list.append(course_name)
        course_number_list.append(course_number)
        course_dict[course_number] = Course(course_name, course_number)

#requisities -> extract requisite column out of the html file.

def extract_requisites(b, requisites, description):
    elements = b.find_elements(By.CLASS_NAME, "courseblockextra.noindent.clearfix")
    for element in elements:
        if str(element.get_attribute("innerHTML").split(":")[0])[-10:] == "Requisites":
            requisite = element.get_attribute("innerHTML").split('<span class="cbextra-data">')[1][:-7]
            requisites.append(requisite)
    for requisite in requisites:
        description.append(remove_link(requisite))
        
# 1. remove link code -> each course has a full requisite statement.
# 2. remove unncessary sentences among the statement.
# 3. split each sentence by using divider 'and'. the length of list is the number of requisites. 


def refine_description(description):
    
    for i in range(len(description)):
        sentences = description[i].split(".")
        for j in range(len(sentences)):
            #remove sentence containing "not"
            if sentences[j].lower().find("not") != -1:
                sentences[j] = ""
            #remove sentence that doesn't contain number
            elif len(re.findall(number3_pattern, sentences[j])) == 0:
                sentences[j] = ""
            #replace 'and' with & for the one enclosed by parenthesis
            elif len(re.findall(parenthesis_and_pattern, sentences[j])) != 0:
                converted = re.findall(parenthesis_and_pattern, sentences[j])
                for k in range(len(converted)):
                    converted[k] = converted[k].replace("and", "&&")
                sentences[j] = re.sub(parenthesis_and_pattern, "TO_BE_SUBSTITUTED", sentences[j])
                sentences[j] = replace_with_list(sentences[j], converted, "TO_BE_SUBSTITUTED")

            #divide each case by and. each component is a component.
            sentences[j] = num3(sentences[j], "and", False)
            for k in range(len(sentences[j])):
                # divide and concatenate with various dividers, removing those and pieces that don't contain numbers
                sentences[j][k] = num3(sentences[j][k], ";")
                sentences[j][k] = num3(sentences[j][k], "or")
                sentences[j][k] = num3(sentences[j][k], ",")

        description[i] = sentences

# refine each component separated by 'and', store them in requisite list of each course.

def parse_and_save(description, course_number_list, course_dict):
# each course descrption
    for i in range(len(description)):
        
        # each sentence in a descrption
        for j in range(len(description[i])):

            # skip it if it contains nothing; it mean it has no number comment in a sentence
            if description[i][j] != ['']:

                # if it contains something related to number, that's the chuck we want to deal with.
                for k in range(len(description[i][j])):
                    description[i][j][k] = description[i][j][k].strip()
                    if description[i][j][k] == '':
                        pass
                    combination_chunk = []
    
                    # deal with those cases enclosed with () first.
                    if len(re.findall(parenthesis_pattern, description[i][j][k])) != 0:
                        parentheses = re.findall(parenthesis_pattern, description[i][j][k])
                        for parenthesis in parentheses:

                            # if it has &&, that means you need to take both courses. Deal with this special case by making it into tuple.
                            # once generated, add each course to requisite set and add the tuple to combination chunk list, which is a component of combination tuple.
                            if parenthesis.find("&&") != -1:
                                parenthesis = re.findall(name_element_pattern, parenthesis)
                                courses = tuple(course_generator(parenthesis))
                                for course in courses:
                                    course_dict[course_number_list[i]].requisite.add(course)
                                combination_chunk.append(courses)
                            
                            # typical 'or' list.
                            else:
                                parenthesis = re.findall(name_element_pattern, parenthesis)
                                courses = course_generator(parenthesis)
                                
                                for course in courses:
                                    course_dict[course_number_list[i]].requisite.add(course.strip())
                                    combination_chunk.append(course.strip())

                    # once dealing with () cases, replace their traces with '', and repeat the process.
                    description[i][j][k] = re.sub(parenthesis_pattern, "", description[i][j][k]).strip()
                    name_elements = re.findall(name_element_pattern, description[i][j][k])
                    courses = course_generator(name_elements)
                    for course in courses:
                        course_dict[course_number_list[i]].requisite.add(course.strip())
                        combination_chunk.append(course.strip())
                    if combination_chunk != []:
                        course_dict[course_number_list[i]].combination.append(combination_chunk)
                        
def main():
    url_list = ["https://guide.wisc.edu/courses/comp_sci/", "https://guide.wisc.edu/courses/math/"]
    course_dict = {}
    file_path = 'example_graph.png'
    
    for url in url_list:

        course_name_list = []
        course_number_list = []
        requisites = []
        description = []

        b.get(url)

        course_name_number_class(b, course_name_list, course_number_list, course_dict)
        extract_requisites(b, requisites, description)
        refine_description(description)
        parse_and_save(description, course_number_list, course_dict)
        
    g = Digraph(strict=True)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # input_list = ['COMP SCI 564', 'COMP SCI 537', 'COMP SCI 577', 'COMP SCI 570']
    # for course in input_list:
    #     graph_generator(course, course_dict, g)
        
        
    graph_generator('COMP SCI/​E C E/​M E 539', course_dict, g)
    g.render('example_graph', format='png')
                        
if __name__ == "__main__":
    main()
