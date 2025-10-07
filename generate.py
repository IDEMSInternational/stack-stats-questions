# pip install python-slugify
from slugify import slugify
import lxml.etree as ET

import os


class PTXStructuralElement:
    # Abstract class properties: element_name

    def __init__(self, title, introduction, questions=None, children=None):
        self.title = title
        self.title_slug = slugify(self.title)
        self.introduction = introduction
        self.questions = questions or []
        self.children = children or []
        self.foldername = f"{self.title_slug}"
        self.filename = f"{self.title_slug}.ptx"
        # abstract properties:
        # xml_id

    def add_question(self, question):
        self.questions.append(question)

    def add_child(self, child):
        self.children.append(child)
    
    @property
    def rel_path(self):
        # Path relative to parent
        return os.path.join(self.foldername, self.filename)

    def render(self, basepath):
        element_name = type(self).element_name
        child_includes = "\n".join([child.get_include() for child in self.children])
        question_includes = "\n".join([question.render(basepath) for question in self.questions])

        return f'''
        <{element_name} xml:id="{self.xml_id}" xmlns:xi="http://www.w3.org/2001/XInclude">
            <title>{self.title}</title>
            <introduction>
                {self.introduction}
                {question_includes}
            </introduction>
            {child_includes}
        </{element_name}>
        '''

    def make_files(self, basepath):
        # basepath is the path that will contain the ptx file and
        # subfolders of this element
        full_path = os.path.join(basepath, self.filename)
        with open(full_path, "w") as f:
            f.write(self.render(basepath))
        for child in self.children:
            child_path = os.path.join(basepath, child.foldername)
            os.makedirs(child_path, exist_ok=True)
            child.make_files(child_path)

    def get_include(self):
        return f'<xi:include href="{self.rel_path}" />'


class PTXMain(PTXStructuralElement):
    def __init__(self, title, introduction, questions=None, children=None):
        super().__init__(title, introduction, questions, children)
        self.foldername = "."
        self.filename = "main.ptx"
    
    def render(self, basepath=None):
        child_includes = "\n".join([child.get_include() for child in self.children])

        return f'''<?xml version="1.0" encoding="utf-8"?>

            <pretext xml:lang="en-US" xmlns:xi="http://www.w3.org/2001/XInclude">
            <!-- we first include a file which contains the docinfo element: -->
            <xi:include href="./docinfo.ptx" />

            <book xml:id="{self.title_slug}">
                <title>{self.title}</title>

                <!-- Include frontmatter -->
                <xi:include href="./frontmatter.ptx" />

                <!-- Include chapters -->
                {child_includes}
                
                <!-- Include backmatter -->
                <xi:include href="./backmatter.ptx" />

            </book>
            </pretext>
            '''


class PTXChapter(PTXStructuralElement):
    element_name = "chapter"

    def __init__(self, title, introduction, questions=None, children=None):
        super().__init__(title, introduction, questions, children)
        # self.path = f"{self.title_slug}/ch-{self.title_slug}.ptx"
        self.xml_id = f"ch-{self.title_slug}"


class PTXSection(PTXStructuralElement):
    element_name = "section"

    def __init__(self, title, introduction, questions=None, children=None):
        super().__init__(title, introduction, questions, children)
        # self.path = f"sections/sec-{self.title_slug}.ptx"
        self.xml_id = f"sec-{self.title_slug}"


class PTXSubsection(PTXStructuralElement):
    element_name = "subsection"

    def __init__(self, title, introduction, questions=None, children=None, parent_section_slug=None):
        super().__init__(title, introduction, questions, children)
        # self.parent_section_slug = parent_section_slug
        # self.path = f"subsections/sec-{self.parent_section_slug}/subsec-{self.title_slug}.ptx"
        self.xml_id = f"subsec-{self.title_slug}"


class PTXStackQuestion:
    def __init__(self, filepath):
        self.filepath = filepath
        self.xmlid = slugify(filepath)
        with open(filepath) as f:
            tag = ET.parse(f).xpath("/quiz/question/name/text")
            tag[0].tag = "title"
            self.title_tag = ET.tostring(tag[0]).decode()
    
    def render(self, relative_to):
        rel_path = os.path.relpath(self.filepath, relative_to)
        return f"""
            <exercise>
                {self.title_tag}

                <!--<introduction>
                    <p></p>
                </introduction>-->

                <!-- A @label is required, becomes a filename in output -->
                <stack label="{self.xmlid}" xmlns:xi="http://www.w3.org/2001/XInclude">
                    <xi:include href="{rel_path}" />
                </stack>
            </exercise>
            """


'''

- Iterate over question bank folder structure.
- parse all gitsync_category.xml (to get category names)

- Folder names --> Chapter, Section, Subsection
- If we have questions in a higher level, add them to the introduction

'''

level_map = {
    0: PTXMain,
    1: PTXChapter,
    2: PTXSection,
    3: PTXSubsection,
}

def compile_structural_element(basepath, title, level=1):
    # TODO: if level == 3, we might bottom out and collect everythign
    paths = os.listdir(basepath)
    if "gitsync_category.xml" in paths:
        with open(os.path.join(basepath, "gitsync_category.xml")) as f:
            tag = ET.parse(f).xpath("/quiz/question/category/text")
            # TODO: Escape <,>,& chars
            title = tag[0].text.split('/')[-1]

    elem_type = level_map[level]
    ptx_elem = elem_type(title, "")
    for rel_path in paths:
        full_path = os.path.join(basepath, rel_path)
        if os.path.isdir(full_path):
            if level < 3:
                child = compile_structural_element(full_path, rel_path, level+1)
                ptx_elem.add_child(child)
        elif rel_path.endswith(".xml") and rel_path != "gitsync_category.xml":
            # TODO: Validate that this is a STACK question (try block)
            question = PTXStackQuestion(full_path)
            ptx_elem.add_question(question)
    return ptx_elem

ptx_main = compile_structural_element("source/stack", "Stats Gold", level=0)
ptx_main.make_files("source")