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
    Creates a question-answering chain using a chat model.

    The chain is configured to act as a helpful assistant that answers user
    questions. Before providing an answer, the chain assesses the uncertainty
    of its response. If the uncertainty is greater than 0.3, it prompts the
    user to reformulate the question and suggest necessary clarifications for
    a better answer.

    Returns:
        A chain object capable of processing user questions and generating 
        responses based on the configured prompts and chat model.
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


def get_current_weather_chain():
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

def get_lazy_prompt(prompt:str, task:str)->str:
    CHAT_MODEL = os.getenv("OPENAI_LZP_MODEL") 
    chat_model = ChatOpenAI(model=CHAT_MODEL, temperature=0)

    chat_prompt_template_propmtmaker = hub.pull("hardkothari/prompt-maker")
    propmtmaker_chain = chat_prompt_template_propmtmaker | chat_model

    answer =f"""ENHANCED PROMPT FOR TASK:\n {propmtmaker_chain.invoke({"task": task, "lazy_prompt": prompt}).content}
    \nbefore your answer, asses the uncertainty of your answer. If its greater then 0.1, ask me clarification questions untill the uncertainty is 0.1 or lower"
    "\n--- END OF ENHANCED PROMPT ---"""
    return answer



def get_tools():
    basic_question_chain = get_basic_question_chain()
    current_weather_chain = get_current_weather_chain()

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
        lazy_prompt_tool,
    ]

    return tools