import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from unidecode import unidecode as accent_remover
from urllib.parse import unquote
from PyPDF2 import PdfFileReader
from io import BytesIO
from datetime import datetime
from time import perf_counter
import streamlit as st

# Pour obtenir uniquement les ALDs, debug_var doit être égal à True
debug_var = True

pd.set_option('display.width', 70000000)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)

df_bioguid_full = pd.DataFrame()

# ======================================================================================================================
# ====================================================== Fonction ======================================================
# ======================================================================================================================

# Obtenir la date du pdf augmente considérablement le temps de chargement

@st.cache
def get_date_from_pdf(pdf_url, debug=True):
    if not debug:

        # N'intérompt pas le code sir le fichier est un zip
        if '.zip' in pdf_url:
            return 'ZIP DETECTÉ'

        # Lit le document
        pdf = PdfFileReader(BytesIO(requests.get(pdf_url).content))

        # Renvoit la date de création du pdf
        creation_date = re.findall(r'\d{8}', pdf.getDocumentInfo()['/CreationDate'].replace('D:', ''))[0]

        # Transforme la date en format 'datetime.datetime'
        datetime_date = datetime.strptime(creation_date, '%Y%m%d')

        # Transforme la date sous un format lisible
        date_fr_fr = datetime_date.strftime("%d/%m/%Y")
        # date_en_us = datetime_date.strftime("%m/%d/%Y")

        return date_fr_fr
    else:
      return 'pdf_date'
      
    
liste_patho = ['allergies alimentaires', 'allergies respiratoires',
               'allergènes spécifiques', 'anémie hémolytique auto-immune',
               'bilan de thrombophilie (facteur biologique de risque)',
               'bilharziose', 'carence en fer', 'chlamydia trachomatis',
               'cirrhose non compliquée', 'coqueluche', 'covid long',
               'dénutrition', "dépistage cancer du col de l'utérus",
               'dépistage de la maladie rénale chronique',
               'dépistage dysthyroïdie', 'helicobacter pylori',
               'herpès cutanéo-muqueux', 'hypoparathyroïdie',
               'hémoglobinopathies', 'hépatite auto-immune',
               'infections génitales basses (cervicite non compliquée)', 'llc',
               'lupus systémique', 'maladie coeliaque', 'maladie de lyme',
               'maladie de willebrand', 'maladie de wilson', 'méno/métrorragies ',
               'ménopause', 'pancréatite aigüe', 'polyarthrite rhumatoïde',
               'prescription non spécifique', 'spondyloarthrite', 'syphilis',
               'tsh basse 1er bilan', 'tsh élevée 1er bilan', 'urétrite',
               'vascularite nécrosante systémique', 'vha', 'vhb', 'vhc', 'vhe',
               'vih']

total_time = perf_counter()

for word_to_look_for in liste_patho:
    # ======================================================================================================================
    # ====================================== Ouvre le code de la page après recherche ======================================
    # ======================================================================================================================

    # Recherche les mots voulus dans le titre des articles avec les filtres suivants:
    # Types : « Médicaments, dispositifs et actes médicaux » & « Recommendations et guides »
    # Nombre d'articles par page : 100 (maximum possible)

    base_url = 'https://www.has-sante.fr/jcms/fc_2875171/fr/resultat-de-recherche?liaison_word-empty=and&expression=exact&text=' + \
              re.sub(r'\s', '+', accent_remover(word_to_look_for)) + '&searchOn=vTitle&catMode=or&dateMiseEnLigne=indexDateFrom&dateDebut=&dateFin=&typesf=technologies%2Fgenerated.AVISProduitsEtPrestations&typesf=technologies%2Fgenerated.EvaluationDesTechnologiesDeSante&typesf=guidelines%2Fgenerated.EtudeEtEnquete&typesf=guidelines%2Fgenerated.EvaluationDesPratiques&typesf=guidelines%2Fgenerated.EvaluationDesProgrammesEtPolitiq&typesf=guidelines%2Fgenerated.GuideMedecinALD&typesf=guidelines%2Fgenerated.Panorama&typesf=guidelines%2Fgenerated.RecommandationsProfessionnelles&search_antidot=OK&replies=100'

    # Permet d'accéder au code de la page pour récupérer les données souhaitées
    user_agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1)'}

    page_soup = BeautifulSoup(requests.get(base_url, headers=user_agent).text, 'html.parser')

    # ======================================================================================================================
    # ============================= Renvoit le nombre de résultats en fonction de la recherche =============================
    # ======================================================================================================================

    # Supprime tout type d'espace (tabulation, espace insécable...) et renvoit uniquement le nombre de résultats
    number_of_results = int(re.findall(r'\d+', re.sub(r'\s', '', page_soup.find_all('h1')[0].text))[0])

    # Définit le nombre de pages à checker en fonction du nombre de résultat
    number_of_pages = int(number_of_results / 100) + 2 if number_of_results > 99 else 2

    print("========================================================================================================================================")

    if number_of_results == 0:
        print('Aucun article trouvé pour', word_to_look_for)
        continue

    t1 = perf_counter()
    # ======================================================================================================================
    # ================================= Effectue une boucle parmi tous les articles trouvés ================================
    # ======================================================================================================================
    suspended_article = 0
    df_bioguid = pd.DataFrame(columns=['pathologie', 'titre_article', 'lien_article', 'type_article', 'date_post_article', 'date_maj_article', 'date_finale_article', 'liens_pdf'])
    article_dict_for_df = dict()
    article_dict_for_df['pathologie'] = word_to_look_for

    print(f"{number_of_results} article(s) trouvé(s) pour « {word_to_look_for} »")

    for page_number in range(1, number_of_pages):
        #print(f'Page n°{page_number}/{number_of_pages - 1}\n')

        # Effectue une nouvelle requête de page uniquement si plus de 100 résultats
        if page_number > 1:
            page_url = base_url + '&page=' + str(page_number)
            page_soup = BeautifulSoup(requests.get(page_url, headers=user_agent).text, 'html.parser')

        # Dictionnaire pour le dataframe
        articles_title_url = dict()

        # Renvoit un dictionnaire avec le titre et l'url des articles présents
        for article in page_soup.find_all('div', {"class": "content"}):
            article_title = article.find('a').text.strip('\r\n\t')

            # Ignore l'article si celui-ci est suspendu
            if 'recommandation' and 'suspendue' in article_title:
                suspended_article += 1
                continue

            # DEBUG, NE SELECTIONNE QUE L'ARTICLE ALD
            # Si un article commence par ALD dans la liste de résultats
            if not re.findall(r'^ALD', article_title) and debug_var:
                continue

            article_url = article.find('a').get('href')
            article_type = article.find_all('span', {"class": "types"})[0].text
            # Renvoit les dates de création et modificaiton par page:
            #     Première valeur --> date de création de la page
            #     Deuxième valeur --> date de modification de la page (si présente)
            article_date = re.findall('\d{2}/\d{2}/\d{4}', article.find_all('span', {"class": "date"})[0].text)  

            
            # Ajoute les informations au dictionnaire pour le dataframe
            article_dict_for_df['titre_article'] = article_title
            article_dict_for_df['lien_article'] = 'https://www.has-sante.fr/' + article_url
            article_dict_for_df['type_article'] = article_type
            article_dict_for_df['date_post_article'] = article_date[0] if len(article_date) else None
            article_dict_for_df['date_maj_article'] = article_date[1] if len(article_date) > 1 else None
            article_dict_for_df['date_finale_article'] = article_date[-1] if len(article_date) else None

            print(article_title)
            article_html = requests.get("https://www.has-sante.fr/" + article_url, headers=user_agent)

            # Récupère tous les liens des PDFs dans le bloc Documents
            article_soup = BeautifulSoup(article_html.text, 'html.parser').find_all('div', {"class": "bloc-docs"})

            pdf_dict = list()

            #print('Liste des PDFs :')
            for line_html in article_soup:
                documents_title = line_html.find('h3').text

                if 'Version Anglaise' in documents_title or 'Outils' in documents_title:
                    continue
                print(documents_title)

                pdfs_html = line_html.find_all('a', {"class": 'xvox_skip_voc'})
                pdfs_true_html = line_html.find_all('a', {"class": 'ctxTooltipCard'})

                # Récupère tous les liens des pdfs des articles
                for pdf_html, pdf_true_html in zip(pdfs_html, pdfs_true_html):
                    pdf_title, pdf_href = pdf_true_html.get('title'), unquote(pdf_html.get('href'))
                    pdf_link = pdf_href.replace("https://core.xvox.fr/readPDF/has-sante.fr/", "").replace("+", "%20")

                    # Affiche uniquement le bon pdf pour les ALDs
                    if re.findall(r'^ALD', article_title):
                        if 'apald' in pdf_true_html.get('href') or 'actes-et-prestations' in pdf_true_html.get('href'):
                            print(pdf_link)
                            pdf_list.append({'title': pdf_title, 'date': get_date_from_pdf(pdf_link), 'link': pdf_link})

                    else:
                        print(pdf_link)
                        pdf_list.append({'title': pdf_title, 'date': get_date_from_pdf(pdf_link), 'link': pdf_link})

            # Ajoute une nouvelle colonne au dataframe en fonction de tous les liens pdf
            article_dict_for_df['liens_pdf'] = pdf_list

            df_bioguid = df_bioguid.append(article_dict_for_df, ignore_index=True)
                        
            print('')


        # Affiche le nombre d'articles suspendus par mot recherché
        print(f'{suspended_article} article(s) suspendu(s) pour « {word_to_look_for} »')

    # Calcule le temps d'execution
    print(f"\nTemps d'execution :", round(perf_counter() - t1, 2), 'secondes')


    df_bioguid_full = df_bioguid_full.append(df_bioguid)

print(f"\nTemps total d'execution :", round(perf_counter() - total_time, 2), 'secondes')


st.write(df_bioguid_full)
