 #Install Required Packages
!pip install -q gradio transformers torch accelerate matplotlib pandas requests

#Imports
import gradio as gr
import torch
import matplotlib.pyplot as plt
import pandas as pd
import json
import os
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from huggingface_hub import login

#Load IBM Granite Model
HF_TOKEN = "hf_token"  # Replace with your actual token
model_id = "ibm-granite/granite-3.3-2b-instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id, token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="auto",
    torch_dtype=torch.float16,
    token=HF_TOKEN
)

#Load Hugging Face Sentiment Model
sentiment_pipeline = pipeline("sentiment-analysis")

#Real-Time Chat Function
def ask_granite(prompt):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=200)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

#Sentiment Analysis with Logging
sentiment_counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0}
interaction_log = []

def submit_feedback(text):
    result = sentiment_pipeline(text)[0]
    sentiment_label = result['label'].upper()
    score = round(result['score'] * 100)

    if sentiment_label not in sentiment_counts:
        sentiment_label = "NEUTRAL"

    sentiment_counts[sentiment_label] += 1

    # Log entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "text": text,
        "sentiment": sentiment_label,
        "score": score
    }

    interaction_log.append(entry)

    # Save to CSV
    csv_file = "sentiment_log.csv"
    df = pd.DataFrame([entry])
    df.to_csv(csv_file, mode='a', header=not os.path.exists(csv_file), index=False)

    # Save to JSON
    json_file = "sentiment_log.json"
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
    else:
        data = []
    data.append(entry)
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2)

    return f"Sentiment: {sentiment_label} ({score}%)"

#Dashboard Charts
def plot_dashboard():
    labels = list(sentiment_counts.keys())
    sizes = list(sentiment_counts.values())
    colors = ["green", "red", "gray"]

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%")
    ax.set_title("Overall Sentiment Distribution")
    return fig

def plot_sentiment_trends():
    if not interaction_log:
        return None

    df = pd.DataFrame(interaction_log)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['minute'] = df['timestamp'].dt.strftime('%H:%M')

    fig, ax = plt.subplots(2, 1, figsize=(8, 6))

    # Line chart: Sentiment trend over time
    trend = df.groupby(['minute', 'sentiment']).size().unstack().fillna(0)
    trend.plot(ax=ax[0], marker='o')
    ax[0].set_title("📈 Sentiment Trend Over Time")
    ax[0].set_ylabel("Count")
    ax[0].set_xlabel("Time")

    # Bar chart: Total sentiment count
    totals = df['sentiment'].value_counts()
    totals.plot(kind='bar', ax=ax[1], color=["green", "red", "gray"])
    ax[1].set_title("📊 Sentiment Count")
    ax[1].set_ylabel("Total")
    ax[1].set_xlabel("Sentiment")

    plt.tight_layout()
    return fig

#File Download Helpers
def download_csv():
    with open("sentiment_log.csv", "r") as f:
        return f.read()

def download_json():
    with open("sentiment_log.json", "r") as f:
        return f.read()

#Gradio Interfaces
# Chat Assistant
def chat_interface(user_input):
    prompt = f"Citizen Query: {user_input}\nAI Response:"
    return ask_granite(prompt)

chat_tab = gr.Interface(fn=chat_interface,
                        inputs=gr.Textbox(label="Ask about public services, civic issues, etc."),
                        outputs=gr.Textbox(label="AI Response"),
                        title="🗣️ Real-Time Citizen Assistant")

# Dashboard
sentiment_input = gr.Textbox(label="Submit Feedback")
sentiment_output = gr.Textbox(label="Detected Sentiment")
dashboard_plot = gr.Plot(label="Dashboard")

with gr.Blocks() as dashboard_tab:
    with gr.Row():
        sentiment_input.render()
        sentiment_output.render()
    with gr.Row():
        submit_btn = gr.Button("Analyze Sentiment & Update Dashboard")
        submit_btn.click(fn=submit_feedback, inputs=sentiment_input, outputs=sentiment_output)
        submit_btn.click(fn=plot_sentiment_trends, outputs=dashboard_plot)
    dashboard_plot.render()

    # ✅ Download buttons (use File components)
    with gr.Row():
        csv_file_output = gr.File(label="Download CSV Log")
        json_file_output = gr.File(label="Download JSON Log")

        def serve_csv(): return "sentiment_log.csv"
        def serve_json(): return "sentiment_log.json"

        download_csv_btn = gr.Button("📥 Download CSV")
        download_json_btn = gr.Button("📥 Download JSON")

        download_csv_btn.click(fn=serve_csv, outputs=csv_file_output)
        download_json_btn.click(fn=serve_json, outputs=json_file_output)

# Launch the App (Only 2 tabs now)
app = gr.TabbedInterface(
    interface_list=[chat_tab, dashboard_tab],
    tab_names=["💬 Chat Assistant", "📊 Dashboard"]
)

app.launch()

