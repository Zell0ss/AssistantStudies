from langchain.prompts import (
    PromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
)
from langchain.tools import StructuredTool
from langchain.agents import  Tool
from langchain_openai import ChatOpenAI
from langchain import hub
from pydantic import BaseModel, Field
import dotenv
import os
from weather.openmeteo import get_tempt_prompt

dotenv.load_dotenv()


def get_basic_question_chain():
    """
    Creates a question-answering chain using the chat model.
    Returns:
        A chain object capable of processing user questions and generating responses
    """

    CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL") # gpt-4o
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    basic_question_system_template_str = """You are a helpful assistant. 
    Your job is to answer to the user his questions to the best of your hability. 
    before your answer, asses the uncertainty of your answer. If its greater then 0.3, ask him to redo the question, 
    indicating what clarifications he need made so you can answer better.
    """

    system_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_template(basic_question_system_template_str)
    )

    human_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("{question}")
    )

    messages = [system_prompt, human_prompt]
    template = ChatPromptTemplate.from_messages(messages)

    basic_question_chain = template | chat_model

    return basic_question_chain

"""
winebot chains
"""
def get_wine_taste_note_chain():

    CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL") # gpt-4o
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    wine_taste_note_system_template_str = """As an expert sommelier, using the information provided including the wine's name, winery, region, grape varietals, your visual, olfactory, and gustatory tasting notes, as well as your personal ratings for acidity, tannins, finish, fruitiness, oak influence, and body, please gather any missing details and craft a descriptive and professional wine tasting note.
Ensure that your note captures the essence of the wine, its unique characteristics, and overall quality in a manner that would resonate with wine enthusiasts and connoisseurs. Emphasize the sensory experience, flavor profile, and any notable nuances that make this wine stand out.
Your tasting note should be articulate, informative, and engaging, providing a comprehensive overview that showcases your expertise and appreciation for fine wines if possible it can include food pairing, bottle prize and a link to the winery website. Aim to create a narrative that transports the reader to the vineyards and evokes the sensory journey of tasting this exceptional wine. 
    before your answer, asses the uncertainty of your answer. If its greater then 0.3, ask him to redo the question, indicating what clarifications he need made so you can answer better.
    """

    system_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_template(wine_taste_note_system_template_str)
    )

    human_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("{question}")
    )

    messages = [system_prompt, human_prompt]
    template = ChatPromptTemplate.from_messages(messages)

    winetaste_question_chain = template | chat_model

    return winetaste_question_chain

def investigate_wine_chain():

    CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL") # gpt-4o
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    investigate_wine_system_template_str = """As an expert sommelier, very well bersed in buying wines, you are given a wine and you need to locate the information about the winery, the region and the grapes usedf. 
    Try also to provide points from 1 to 5 for the acidity, tanicity, finish, fruityness, oak influence and body, but if you cant for any or all of them is ok: do not return it. 
    If possible provide the price per bottle and a link to the winery website.
    before your answer, asses the uncertainty of your answer. If its greater then 0.3, ask him to redo the question, indicating what clarifications he need made so you can answer better.
    """

    system_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_template(investigate_wine_system_template_str)
    )

    human_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("{question}")
    )

    messages = [system_prompt, human_prompt]
    template = ChatPromptTemplate.from_messages(messages)

    wine_question_chain = template | chat_model

    return wine_question_chain

def get_social_media_banner():
    CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL") # gpt-4o
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    basic_question_system_template_str = """
### Como experto en crear contenido cautivador para redes sociales, tu trabajo es crear una presentación concisa y atractiva adaptada para Twitter, Instagram y Tumblr para promocionar artículos publicados en https://gotasdivinas.blogspot.com/ ofreciendo ideas únicas e información valiosa a tu audiencia.
### La presentación debe ser visualmente atractiva y llamativa, utilizando hashtags e imágenes relevantes para mejorar el alcance y la participación en las tres plataformas.
### Crea un pie de foto convincente que invite a los usuarios a hacer clic en el artículo, destacando sus puntos clave y aspectos intrigantes. Considera el tono y el estilo de cada plataforma para garantizar el máximo impacto y resonancia con tus seguidores.
### Apunta a un mensaje conciso pero impactante que despierte la curiosidad y fomente la interacción, impulsando el tráfico al blog y aumentando la visibilidad delu contenido.
### Recuerda adaptar la presentación para satisfacer los requisitos específicos y las preferencias de la audiencia de Twitter, Instagram y Tumblr, optimizando cada publicación para obtener el máximo efecto en la promoción de tu artículo.
### Retorna una lista deinstrucciones para publicar el post de la presentacion, los hastags, las imagenes, etc para las plataformas indicadas."""
           

    system_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_template(basic_question_system_template_str)
    )

    human_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("{question}")
    )

    messages = [system_prompt, human_prompt]
    template = ChatPromptTemplate.from_messages(messages)

    basic_question_chain = template | chat_model

    return basic_question_chain

"""
weatherbot chains
"""
def get_current_weather_chain():
    """
    Creates a question-answering chain using a chat model that knows the current weather forecast.

    The chain is configured to act as a meteorologist that answers user questions about the current weather.
    The chain is given the current weather forecast as a system prompt and is expected to answer accordingly.

    Returns:
        A chain object capable of processing user questions about the current weather and generating responses based on the configured prompts and chat model.
    """
    CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL") # gpt-4o
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    system_template_str = f"You are a meteorologist. Your job is to answer to what will be todays weather. You know that today's weather forecast is {get_tempt_prompt()}."

    system_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_template(system_template_str)
    )

    human_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("{question}")
    )

    messages = [system_prompt, human_prompt]
    template = ChatPromptTemplate.from_messages(messages)

    question_chain = template | chat_model

    return question_chain

def get_weather_report_chain():
    """
    Creates a question-answering chain using a chat model that knows the current weather forecast.

    The chain is configured to act as a meteorologist that creates a full report about the current weather.
    The chain is given the current weather forecast and a wine saying as a system prompt and is expected to answer accordingly.

    Returns:
        A chain object capable of processing user questions about the current weather and generating responses based on the configured prompts and chat model.
    """
    CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL") # gpt-4o
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    system_template_str =  f"Como experto en redactar columnas meteorológicas atractivas para periódicos, tu tarea es crear una pieza cautivadora con el pronóstico del tiempo de hoy junto con un refrán relacionado. \
Combina el extracto meteorológico con el refrán para formar una columna concisa y entretenida que cautive a tus lectores. \
Considera incluir detalles como la vestimenta recomendada para el día, si la temperatura se ajusta a la estación actual y cualquier fenómeno meteorológico único que valga la pena mencionar. \
Tu columna no solo debe informar a los lectores sobre el clima del día, sino también engancharlos con un toque de creatividad y estilo. \
Redacta una narrativa que entrelace sin esfuerzo el pronóstico del tiempo, el refrán y observaciones adicionales para que tu columna sea tanto informativa como agradable de leer. \
Apunta a una extensión adecuada para una columna de periódico, brindando una visión general breve pero completa del clima del día mientras le imprimes personalidad y encanto. \
Deja que tu experiencia brille mientras entregas una columna meteorológica que no solo informe, sino que también entretenga e intrigue a tu audiencia. \
Prepárate para inspirar a tus lectores con una deliciosa combinación de información meteorológica y sabiduría literaria en la columna del clima de hoy. Aquí estan la temperatura y el refran\ {get_tempt_prompt()}."

    system_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate.from_template(system_template_str)
    )

    human_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate.from_template("{question}")
    )

    messages = [system_prompt, human_prompt]
    template = ChatPromptTemplate.from_messages(messages)

    question_chain = template | chat_model

    return question_chain

"""
Misc chains
"""
def get_lazy_prompt(prompt:str, task:str)->str:
    CHAT_MODEL = os.getenv("OPENAI_LZP_MODEL") 
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    chat_prompt_template_propmtmaker = hub.pull("hardkothari/prompt-maker")
    propmtmaker_chain = chat_prompt_template_propmtmaker | chat_model

    answer =f"""ENHANCED PROMPT FOR TASK:\n {propmtmaker_chain.invoke({"task": task, "lazy_prompt": prompt}).content}
    \nbefore your answer, asses the uncertainty of your answer. If its greater then 0.1, ask me clarification questions untill the uncertainty is 0.1 or lower"
    "\n--- END OF ENHANCED PROMPT ---"""
    return answer


"""
tool creation
"""
def get_tools():
    """
    Returns a list of tools for the agent to use.

    The tools are:
        - BasicQuestions: A tool that answers all kind of questions except if they are about the weather today, or about generate propmpts based on the instructions in the received one.
        - WeatherSummary: A tool that answers questions about the current weather today.
        - LazyPrompt: A tool that takes a prompt and a task and returns an enhanced version of the prompt that should be presented to the user as-is, not executed.
    """
    basic_question_chain = get_basic_question_chain()
    current_weather_chain = get_current_weather_chain()
    weather_report_chain = get_weather_report_chain()    
    wine_taste_note_chain = get_wine_taste_note_chain()
    wine_details_chain = investigate_wine_chain()
    social_media_banner = get_social_media_banner()

    # for tools that call a function with parameter passing we need to create the model of the parameters 
    # with its description for the LLM and then create an StructuredTool
    ## LazyPrompt
    class LazyPromptInput(BaseModel):
        prompt: str = Field(description="The original prompt to be enhanced")
        task: str = Field(description="The task or purpose the prompt is for")
    lazy_prompt_tool = StructuredTool(
                        name="LazyPrompt",
                        description="Use when asked to enrich, expand or make better a prompt. Requires the original prompt and the task it's designed for. This tool returns an enhanced version of the prompt that should be presented to the user as-is, not executed.",
                        func=get_lazy_prompt,
                        args_schema=LazyPromptInput
                    )
    

    tools = [
        Tool(
            name="BasicQuestions",
            func=basic_question_chain.invoke,
            description="""Useful when you need to answer all kind of questions except if they are about the
            weather today, or about generate propmpts based on the instructions in the received one. Use the
            entire prompt as input to the tool. For instance, if the prompt is
            "How big is the city of Oviedo?", the input should be "How big is the city of Oviedo?".
            """,
        ),
        Tool(
            name="WeatherSummary",
            func=current_weather_chain.invoke,
            description="Use when asked about current weather today.",
        ),
        Tool(
            name="WeatherReport",
            func=weather_report_chain.invoke,
            description="Use when asked about make a complete report or an inspired piece, newspaper-like, about current weather today.",
        ),
        Tool(
            name="WineTasteNote",
            func=wine_taste_note_chain.invoke,
            description="Use when asked to generate a wine tasting note with the wine data provided.",
        ),
        Tool(
            name="WineArticleBanner",
            func=social_media_banner.invoke,
            description="Use when asked to promote in social networks an article passed or described to you.",
        ),
        Tool(
            name="InvestigateWine",
            func=wine_details_chain.invoke,
            description="Use when asked to investigate a wine. The question must specify that it's about wine details.",
        ),
        lazy_prompt_tool,
    ]

    return tools