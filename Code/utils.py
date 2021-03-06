import codecs
import csv
import os
import pickle
import platform
import random
import re
import string
import copy
from collections import defaultdict
import pprint

import nltk
import numpy as np
from nltk import word_tokenize
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
from nltk.stem.snowball import SnowballStemmer
from nltk.stem.wordnet import WordNetLemmatizer

from sklearn.model_selection import train_test_split

porter = PorterStemmer()
snowball = SnowballStemmer('english')
wordnet = WordNetLemmatizer()

CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'

SUBJECT_ADA = 'ADA'
SUBJECT_OS = 'OS'

mapping_cog = {'Remember': 0, 'Understand': 1, 'Apply': 2, 'Analyse': 3, 'Evaluate': 4, 'Create': 5}
mapping_cog2 = {v : k for k, v in mapping_cog.items()}
mapping_know = {'Factual': 0, 'Conceptual': 1, 'Procedural': 2, 'Metacognitive': 3}

if(platform.system() == 'Windows'):
    stopwords = set(re.split(r'[\s]', re.sub('[\W]', '', open(os.path.join(os.path.dirname(__file__), 'resources/stopwords.txt'), 'r', encoding='utf8').read().lower(), re.M), flags=re.M) + [chr(i) for i in range(ord('a'), ord('z') + 1)])
else:
    stopwords = set(re.split(r'[\s]', re.sub('[\W]', '', open(os.path.join(os.path.dirname(__file__), 'resources/stopwords.txt'), 'r').read().lower(), re.M), flags=re.M) + [chr(i) for i in range(ord('a'), ord('z') + 1)])
stopwords.update(['.', ',', '"', "'", '?', '!', ':', ';', '(', ')', '[', ']', '{', '}'])

regex = re.compile('[%s]' % re.escape(string.punctuation))
#see documentation here: http://docs.python.org/2/library/string.html


########################### PREPROCESSING UTILITY CODE ###########################
def clean(sentence, stem=True, lemmatize=True, return_as_list=True):
    sentence = re.sub('-\n', '', sentence).lower()
    sentence = re.sub('\n', ' ', sentence)
    sentence = re.sub('[^a-z.?! ]', '', sentence)

    final_sentence = []
    for word in word_tokenize(sentence):
        word = regex.sub(u'', word)
        if not (word == u'' or word == ''):
            if lemmatize:
                word = wordnet.lemmatize(word)
            if stem:
                word = porter.stem(word)
            
            final_sentence.append(word)

    return final_sentence if return_as_list else ' '.join(final_sentence)

def clean2(text):
    tokens = [word for word in nltk.word_tokenize(text) if word.lower() not in stopwords]
    return ' '.join(list(set([porter.stem(i) for i in [j for j in tokens if re.match('[a-zA-Z]', j) ]])))

def clean_no_stopwords(text, stem=True, lemmatize=True, as_list=True):
    text = re.sub('-\n', '', text).lower()
    text = re.sub('-', ' ', text)
    text = re.sub('\n', ' ', text)
    text = re.sub('[^a-z.?! ]', '', text)
    tokens = [w for w in text.lower().split() if w.isalpha()]
    
    if lemmatize:
        tokens = [wordnet.lemmatize(w) for w in tokens]

    if stem:
        tokens = [porter.stem(w) for w in tokens]
    
    if as_list:
        return tokens
    else:
        return ' '.join(tokens)

def shuffleXY(X, Y):
    data = list(zip(X, Y))
    random.shuffle(data)

    X = [x[0] for x in data]
    Y = [x[1] for x in data]

    return X, Y

def shuffle_generic(*args):
    data = list(zip(*args))
    random.shuffle(data)

    args = []
    for i in range(len(data[0])):
        args.append([x[i] for x in data])

    return args

def splitXY(X, Y, split):
    assert len(X) == len(Y), 'ValidationError: lengths of X and Y are not equal'

    X_part1 = X[ : int(len(X) * split)]
    Y_part1 = Y[ : int(len(X) * split)]

    X_part2 = X[int(len(X) * split) : ]
    Y_part2 = Y[int(len(X) * split) : ]

    return X_part1, Y_part1, X_part2, Y_part2



################ GLOVE RETRIEVAL CODE #######################
def get_glove_vectors(path):
    with open(os.path.join(os.path.dirname(__file__), path), "r", encoding='latin-1') as lines:
        __w2v = {}
        for row, line in enumerate(lines):
            try:
                w = line.split()[0]
                vec = np.array(list(map(float, line.split()[1:])))
                __w2v[w] = vec
            except:
                continue
            finally:
                if((row + 1) % 100 == 0):
                    print(CURSOR_UP_ONE + ERASE_LINE + 'Processed {} GloVe vectors'.format(row + 1))

    return __w2v


########################### PROB. DIST MODIFIER ###########################

def get_modified_prob_dist(probs):
    i = np.argmax(probs)

    xs = 0.0
    for j in range(i + 1, len(probs)):
        xs += probs[j]
        probs[j] = 0

    num_xs = len(probs) - (i + 1)
    if num_xs > 0:
        probs[:i + 1] +=  xs / num_xs

    return probs

########################### SKILL: QUESTION FILTERER ###########################

domain = None
sklearn_tfidf_ada = pickle.load(open(os.path.join(os.path.dirname(__file__), 'models/tfidf_filterer_ada.pkl'), 'rb'))
sklearn_tfidf_os = pickle.load(open(os.path.join(os.path.dirname(__file__), 'models/tfidf_filterer_os.pkl'), 'rb'))

def get_filtered_questions(questions, threshold=0.25, what_type='os'):
    global domain
    t_stopwords = set(nltk.corpus.stopwords.words('english'))

    if not domain:
        domain = pickle.load(open(os.path.join(os.path.dirname(__file__), 'resources/domain.pkl'),  'rb'))  

    keywords = set()
    for k in domain:
        keywords = keywords.union(set(list(map(str.lower, map(str, list(domain[k]))))))
    t_stopwords = t_stopwords - keywords

    if type(questions) != type([]):
        questions = [questions]

    sklearn_tfidf = None
    if what_type.lower() == 'os':
        sklearn_tfidf = sklearn_tfidf_os
    else:
        sklearn_tfidf = sklearn_tfidf_ada
        
    tfidf_matrix = sklearn_tfidf.transform(questions)
    feature_names = sklearn_tfidf.get_feature_names()

    max_idf = max(sklearn_tfidf.idf_)

    new_questions = []

    for i in range(0, len(questions)):
        feature_index = tfidf_matrix[i,:].nonzero()[1]
        tfidf_scores = zip(feature_index, [tfidf_matrix[i, x] for x in feature_index])
        word_dict = defaultdict(lambda: max_idf)
        word_dict.update({w : s for w, s in [(feature_names[j], s) for (j, s) in tfidf_scores]})

        question = re.sub(' [^a-z]*? ', ' ', questions[i].lower())
        question = re.split('([.!?])', question)

        sentences = []
        for k in range(len(question) - 1):
            if re.search('[!.?]', question[k + 1]):
                sentences.append(question[k] + question[k + 1])
            elif re.search('[!.?]', question[k]):
                continue
            elif question[k] != '':
                sentences.append(question[k].strip())

        if len(sentences) >= 3:
            q = sentences[0] + ' ' + sentences[-2]
            q += ' ' + sentences[-1] if 'hint' not in sentences[-1] else ''
            questions[i] = q

        new_question = ''
        for word in re.sub('[^a-z ]', '', questions[i].lower()).split():
            if word.isalpha() and (word_dict[word] < threshold or word in keywords) and word not in t_stopwords:
                new_question += word + ' '

        new_questions.append(new_question.strip())

    return new_questions if len(new_questions) > 1 else new_questions[0]

########################### SKILL: GET FILTERED DATA FROM APPROPRIATE DATASETS ###########################

def get_data_for_cognitive_classifiers(threshold=[0, 0.1, 0.15], what_type=['ada', 'os', 'bcl'], what_for='train', include_keywords=True, keep_dup=False, shuffle=True):
    X_data = []
    X_data_orig = []
    Y_data = []

    if what_for == 'test':
        include_keywords = False
        suffix = '_v2_test'
    else:
        suffix = '_v2'

    if 'ada'in what_type:
        with open(os.path.join(os.path.dirname(__file__), 'datasets/ADA_Exercise_Questions_Labelled%s.csv' %suffix), 'r', encoding='latin-1') as csvfile:
            X_data_temp = []
            Y_data_temp = []
            all_rows = csvfile.read().splitlines()[1:]
            csvreader = csv.reader(all_rows)
            for row in csvreader:
                if row:
                    sentence, label_cog, label_know = row
                    m = re.match('(\d+\. )?([a-z]\. )?(.*)', sentence)
                    sentence = m.groups()[2]
                    label_cog = label_cog.split('/')[0]
                    clean_sentence = clean(sentence, stem=False, lemmatize=False, return_as_list=False)
                    X_data_temp.append(clean_sentence)
                    Y_data_temp.append(mapping_cog[label_cog])

        for t in threshold:
            X_data_temp_2 = get_filtered_questions(X_data_temp, threshold=t, what_type='ada')
            X_data.extend(X_data_temp_2)
            X_data_orig.extend(X_data_temp)
            Y_data.extend(Y_data_temp)

    if 'os' in what_type:
        with open(os.path.join(os.path.dirname(__file__), 'datasets/OS_Exercise_Questions_Labelled%s.csv' %suffix), 'r', encoding='latin-1') as csvfile:
            X_data_temp = []
            Y_data_temp = []
            all_rows = csvfile.read().splitlines()[5:]
            csvreader = csv.reader(all_rows)
            for row in csvreader:
                if row:
                    shrey_cog, shiva_cog, mohit_cog = row[2].split('/')[0], row[4].split('/')[0], row[6].split('/')[0]
                    label_cog = mohit_cog if mohit_cog else (shiva_cog if shiva_cog else shrey_cog)
                    label_cog = label_cog.strip()
                    if(label_cog == ''):
                        continue
                    clean_sentence = clean(row[0], stem=False, lemmatize=False, return_as_list=False)
                    X_data_temp.append(clean_sentence)
                    Y_data_temp.append(mapping_cog[label_cog])

        for t in threshold:
            X_data_temp_2 = get_filtered_questions(X_data_temp, threshold=t, what_type='os')
            X_data.extend(X_data_temp_2)
            X_data_orig.extend(X_data_temp)
            Y_data.extend(Y_data_temp)

    if 'bcl' in what_type:
        with open(os.path.join(os.path.dirname(__file__), 'datasets/BCLs_Question_Dataset%s.csv' %suffix), 'r', encoding='latin-1') as csvfile:
            X_data_temp = []
            Y_data_temp = []
            all_rows = csvfile.read().splitlines()[1:]
            csvreader = csv.reader(all_rows)
            for row in csvreader:
                if row:
                    sentence, label_cog = row
                    clean_sentence = clean(sentence, stem=False, lemmatize=False, return_as_list=False)
                    X_data_temp.append(clean_sentence)
                    Y_data_temp.append(mapping_cog[label_cog])

        for t in threshold:
            X_data_temp_2 = get_filtered_questions(X_data_temp, threshold=t, what_type='ada')
            X_data.extend(X_data_temp_2)
            X_data_orig.extend(X_data_temp)
            Y_data.extend(Y_data_temp)

    if keep_dup:
        X_data = [x.split() for x in X_data]
    else:
        X_data = [list(np.unique(x.split())) for x in X_data]
    
    if shuffle and len(what_type) > 0:
        X_data, X_data_orig, Y_data = shuffle_generic(X_data, X_data_orig, Y_data)

    if include_keywords:
        domain_keywords = pickle.load(open(os.path.join(os.path.dirname(__file__), 'resources/domain.pkl'), 'rb'))
        for key in domain_keywords:
            for word in domain_keywords[key]:
                X_data.append(clean(word, stem=False, lemmatize=False, return_as_list=True))
                X_data_orig.append(clean(word, stem=False, lemmatize=False, return_as_list=False))
                Y_data.append(mapping_cog[key])

        if shuffle:
            X_data, X_data_orig, Y_data = shuffle_generic(X_data, X_data_orig, Y_data)

    # getting rid of size 0 entries
    data = list(zip(X_data, X_data_orig, Y_data))
    X_data = [x[0] for x in data if len(x[0]) > 0]
    Y_data = [x[-1] for x in data if len(x[0]) > 0]

    if __name__ == '__main__':
        # just printing out unregistered questions
        X_unreg = []
        for x in data:
            if len(x[0]) == 0:
                X_unreg.append(x[1])

        print(X_unreg)

    return X_data, Y_data



##################### KNOWLEDGE: CONVERT PROB TO HARDCODED VECTOR #####################
def get_knowledge_probs(prob):
    hardcoded_matrix = [1.0, 0.6, 0.3, 0.1, 0]
    for i, r in enumerate(zip(hardcoded_matrix[1:], hardcoded_matrix[:-1])):
        if r[0] <= prob < r[1]:
            break
    level = i

    probs = [0.0] * 4
    for i in range(level):
        # probs[i] = (i + 1) * prob / (level * (level + 1) / 2)
        probs[i] = (i + 1) * prob / (level + 1)
    probs[level] = prob

    return probs

##################### KNOWLEDGE: CONVERT level to hardcoded vector ###############

def get_knowledge_probs_level(level, probs):
    probs = [0.0] * 4
    for i in range(level):
        # probs[i] = (i + 1) * prob / (level * (level + 1) / 2)
        probs[i] = (i + 1) * prob / (level + 1)
    probs[level] = prob

    return probs
    
##################### KNOWLEDGE: GET QUESTIONS (relabel.py CODE) #####################

def get_questions_by_section(subject, skip_files, shuffle=True):
    exercise_content = {}
    for filename in sorted(os.listdir(os.path.join(os.path.dirname(__file__), './resources/%s' %subject))):
        with open('./resources/%s/'%subject + filename, encoding='latin-1') as f:
            contents = f.read()
            title = contents.split('\n')[0].strip()
            if len([1 for k in skip_files if (k in title or k in filename)]):
                continue

            match = re.search(r'\n[\s]*Exercises[\s]+([\d]+\.[\d]+)[\s]*(.*)', contents, flags=re.M | re.DOTALL)

            if match:
                exercise_content[title] = '\n' + match.group(2).split('SUMMARY')[0]

        X_data, Y_data = [], []
        for e in exercise_content:
            for question in re.split('[\n][\s]*[\d]+\.', exercise_content[e].strip(), flags=re.M | re.DOTALL):
                if len(question) > 0:
                    X_data.append(re.sub('\n', ' ', re.sub('1\.', '', question.strip()), flags=re.M | re.DOTALL))
                    Y_data.append(e)

    if shuffle:
        X_data, Y_data = shuffleXY(X_data, Y_data)

    return X_data, Y_data

def get_data_for_knowledge_classifiers(subject='ADA', shuffle=True):
    X_data = []
    Y_data = []
    if subject == SUBJECT_ADA:
        with codecs.open(os.path.join(os.path.dirname(__file__), 'datasets/ADA_Exercise_Questions_Labelled.csv'), 'r', encoding="latin-1") as csvfile:
            csvreader = csv.reader(csvfile.read().splitlines()[1:])
            for row in csvreader:
                sentence, label_cog, label_know = row
                m = re.match('(\d+\. )?([a-z]\. )?(.*)', sentence)
                X_data.append(m.groups()[2])
                Y_data.append(mapping_know[label_know.split('/')[0]])

    elif subject == SUBJECT_OS: # return question : knowledge mapping
        with codecs.open('datasets/OS_Exercise_Questions_Labelled.csv', 'r', encoding="latin-1") as csvfile:
            csvreader = csv.reader(csvfile.read().splitlines()[5:])
            for row in csvreader:
                X_data.append(row[0])
                if(row[5] == '' and row[3] == ''):  #Following Mohit > Shiva > Shrey
                    label_know = row[1].split('/')[0]
                    Y_data.append(mapping_know[label_know.strip()])
                elif(row[5] == '' and row[3] != ''):
                    label_know = row[3].split('/')[0]
                    Y_data.append(mapping_know[label_know.strip()])
                else:
                    label_know = row[5].split('/')[0]
                    Y_data.append(mapping_know[label_know.strip()])

    if shuffle:
        X_data, Y_data = shuffleXY(X_data, Y_data)

    return X_data, Y_data


if __name__ == '__main__':
    ########### train - test split code - ada / os / bcl ##############
    X_ada, X_os, X_bcl = [], [], []
    Y_ada, Y_os, Y_bcl = [], [], []

    # read all csv files and keep track of which question belongs to which type
    with open(os.path.join(os.path.dirname(__file__), 'datasets/ADA_Exercise_Questions_Labelled.csv'), 'r', encoding='latin-1') as csvfile:
        all_rows = csvfile.read().splitlines()[1:]
        csvreader = csv.reader(all_rows)
        for row in csvreader:
            sentence, label_cog, label_know = row
            m = re.match('(\d+\. )?([a-z]\. )?(.*)', sentence)
            sentence = m.groups()[2]
            label_cog = label_cog.split('/')[0]
            X_ada.append(sentence)
            Y_ada.append(mapping_cog[label_cog])

    with open(os.path.join(os.path.dirname(__file__), 'datasets/OS_Exercise_Questions_Labelled.csv'), 'r', encoding='latin-1') as csvfile:
        all_rows = csvfile.read().splitlines()[5:]
        csvreader = csv.reader(all_rows)
        for row in csvreader:
            shrey_cog, shiva_cog, mohit_cog = row[2].split('/')[0], row[4].split('/')[0], row[6].split('/')[0]
            label_cog = mohit_cog if mohit_cog else (shiva_cog if shiva_cog else shrey_cog)
            label_cog = label_cog.strip()
            X_os.append(row[0])
            Y_os.append(mapping_cog[label_cog])

    with open(os.path.join(os.path.dirname(__file__), 'datasets/BCLs_Question_Dataset.csv'), 'r', encoding='latin-1') as csvfile:
        all_rows = csvfile.read().splitlines()[1:]
        csvreader = csv.reader(all_rows)
        for row in csvreader:
            sentence, label_cog = row
            X_bcl.append(sentence)
            Y_bcl.append(mapping_cog[label_cog])

    data_ada, data_os, data_bcl = {}, {}, {}

    data_ada = { k[0] : k[1] for k in enumerate(list(zip(X_ada, Y_ada))) }
    data_os = { len(data_ada) + k[0] : k[1] for k in enumerate(list(zip(X_os, Y_os))) }
    data_bcl = { len(data_ada) + len(data_os) + k[0] : k[1] for k in enumerate(list(zip(X_bcl, Y_bcl))) }

    data_combined = copy.deepcopy(data_ada)
    data_combined.update(data_os)
    data_combined.update(data_bcl)

    index = []
    x_data = []
    y_data = []
    for k, v in data_combined.items():
        index.append(k)
        x_data.append(v[0])
        y_data.append(v[1])

    index, x_data, y_data = shuffle_generic(index, x_data, y_data)

    data_combined = list(zip(index, x_data, y_data))

    data_train = data_combined[: int(len(data_combined) * 0.7)]
    data_test = data_combined[int(len(data_combined) * 0.7) :]

    X_ada_train, X_os_train, X_bcl_train = [], [], []
    Y_ada_train, Y_os_train, Y_bcl_train = [], [], []
    for i, x, y in data_train:
        if i in data_ada:
            X_ada_train.append(x)
            Y_ada_train.append(y)
        elif i in data_os:
            X_os_train.append(x)
            Y_os_train.append(y)
        elif i in data_bcl:
            X_bcl_train.append(x)
            Y_bcl_train.append(y)

    X_ada_test, X_os_test, X_bcl_test = [], [], []
    Y_ada_test, Y_os_test, Y_bcl_test = [], [], []
    for i, x, y in data_test:
        if i in data_ada:
            X_ada_test.append(x)
            Y_ada_test.append(y)
        elif i in data_os:
            X_os_test.append(x)
            Y_os_test.append(y)
        elif i in data_bcl:
            X_bcl_test.append(x)
            Y_bcl_test.append(y)


    ################ DUMP TRAINING DATA ################
    with open(os.path.join(os.path.dirname(__file__), 'datasets/ADA_Exercise_Questions_Labelled_v2.csv'), 'w', encoding='latin-1') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['', '', ''])
        for x, y in zip(X_ada_train, Y_ada_train):
            writer.writerow([x, mapping_cog2[y], ''])

    with open(os.path.join(os.path.dirname(__file__), 'datasets/OS_Exercise_Questions_Labelled_v2.csv'), 'w', encoding='latin-1') as csvfile:
        writer = csv.writer(csvfile)
        for i in range(5):
            writer.writerow(['', '', '', '', '', '', ''])
        for x, y in zip(X_os_train, Y_os_train):
            writer.writerow([x, '', mapping_cog2[y], '', '', '', ''])

    with open(os.path.join(os.path.dirname(__file__), 'datasets/BCLs_Question_Dataset_v2.csv'), 'w', encoding='latin-1') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['', ''])
        for x, y in zip(X_bcl_train, Y_bcl_train):
            writer.writerow([x, mapping_cog2[y]])

    ################ DUMP TESTING DATA ################
    with open(os.path.join(os.path.dirname(__file__), 'datasets/ADA_Exercise_Questions_Labelled_v2_test.csv'), 'w', encoding='latin-1') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['', '', ''])
        for x, y in zip(X_ada_test, Y_ada_test):
            writer.writerow([x, mapping_cog2[y], ''])

    with open(os.path.join(os.path.dirname(__file__), 'datasets/OS_Exercise_Questions_Labelled_v2_test.csv'), 'w', encoding='latin-1') as csvfile:
        writer = csv.writer(csvfile)
        for i in range(5):
            writer.writerow(['', '', '', '', '', '', ''])
        for x, y in zip(X_os_test, Y_os_test):
            writer.writerow([x, '', mapping_cog2[y], '', '', '', ''])

    with open(os.path.join(os.path.dirname(__file__), 'datasets/BCLs_Question_Dataset_v2_test.csv'), 'w', encoding='latin-1') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['', '', ''])
        for x, y in zip(X_bcl_test, Y_bcl_test):
            writer.writerow([x, mapping_cog2[y]])
