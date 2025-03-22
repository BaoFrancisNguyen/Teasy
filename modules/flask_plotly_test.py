from flask import Flask, render_template, jsonify
import plotly
import plotly.express as px
import pandas as pd
import json

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('plotly_test.html')

@app.route('/get_plot')
def get_plot():
    # Créer des données de test
    df = pd.DataFrame({
        'x': [1, 2, 3, 4, 5],
        'y': [1, 4, 9, 16, 25]
    })
    
    # Créer un graphique simple
    fig = px.scatter(df, x='x', y='y', title='Test Plotly Graph')
    
    # Convertir en JSON pour l'envoyer au template
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    return jsonify(graphJSON=graphJSON)

if __name__ == '__main__':
    app.run(debug=True, port=5000)