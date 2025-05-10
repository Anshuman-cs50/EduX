from openai import OpenAI

from get_image import fetch_image, show_image

client = OpenAI(
  api_key = "my_api_key"
)


# completion = client.chat.completions.create(
#   model="gpt-4o-mini",
#   store=True,
#   messages=[
#     {"role": "user", "content": ""}
#   ]
# )
# print(completion.choices[0].message.content);


def summarise(text, summary_length="short", style="paragraph", language_level="beginner"):
    prompt = f"""You are a helpful summarization assistant.

Summarize the following content according to the user's preferences and make the summary in as much personalized way as possible. 
Analyse the difficulty level of the text and adjust the language level accordingly.:
- Summary length: {summary_length}
- Format style: {style}
- Language level: {language_level}

Please provide:
1. A short title or topic name. (just a short phrase without any heading)
2. The summary content, as per the specified format and tone.
3. Indicate whether a diagram is typically associated with this topic by returning True or False. (just return True or False. no heading or explanation needed)

Text to summarize:
\"\"\"{text}\"\"\"
"""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return completion.choices[0].message


def get_summary(user, preferences, text):
    """
    main function to get the summary and diagram of the text based on user preferences of the user from the database
    """

    summary = summarise(text, preferences["summary_length"], preferences["style"], preferences["language_level"])

    title = summary.content.split("\n")[0]

    if summary.content.split("\n")[-1].strip() == "True":
        image = fetch_image(title)
        return summary, image
    return summary, None


if __name__ == "__main__":
    user = "user1"
    preferences = {
        "summary_length": "short",
        "style": "paragraph",
        "language_level": "beginner"
    }
    text = "This article explains the invention of the printing press and its impact on literacy in Europe. It also touches on Gutenberg's biography, the political effects of mass communication, and a brief overview of print technology evolution since the 15th century."

    summary, image = get_summary(user, preferences, text)
    print(summary.content.split("\n")[2].strip())
    if image:
        show_image(image, title=summary.content.split("\n")[0].strip())
