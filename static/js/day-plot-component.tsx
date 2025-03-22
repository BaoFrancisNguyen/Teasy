import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import Plot from 'react-plotly.js';
import _ from 'lodash';

const DayPlotCalendar = () => {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedBrand, setSelectedBrand] = useState('all');
  const [brands, setBrands] = useState([]);
  
  // Fonction pour formater les données pour la visualisation du calendrier
  const formatCalendarData = (rawData, brandFilter) => {
    if (!rawData || !rawData.length) return null;
    
    // Filtrer par marque si nécessaire
    const filteredData = brandFilter === 'all' 
      ? rawData 
      : rawData.filter(item => item.magasin === brandFilter);
    
    // Regrouper les données par date
    const groupedByDate = _.groupBy(filteredData, 'date_achat');
    
    // Formater les données pour Plotly
    const dates = [];
    const counts = [];
    
    Object.entries(groupedByDate).forEach(([date, items]) => {
      dates.push(date);
      counts.push(items.length);
    });
    
    return { dates, counts };
  };
  
  // Simuler le chargement des données
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Dans une implémentation réelle, vous feriez un appel API ici
        // Simuler des données pour la démonstration
        const simulatedData = generateSampleData();
        
        setData(simulatedData);
        
        // Extraire les marques uniques pour la liste déroulante
        const uniqueBrands = ['all', ...new Set(simulatedData.map(item => item.magasin))];
        setBrands(uniqueBrands);
        
        setIsLoading(false);
      } catch (err) {
        setError('Erreur lors du chargement des données');
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, []);
  
  // Fonction pour générer des données d'exemple
  const generateSampleData = () => {
    const brands = ['Carrefour', 'Auchan', 'Leclerc', 'Monoprix', 'Franprix'];
    const sampleData = [];
    
    // Générer des données pour les 60 derniers jours
    const endDate = new Date();
    
    for (let i = 0; i < 60; i++) {
      const date = new Date();
      date.setDate(endDate.getDate() - i);
      const dateStr = date.toISOString().split('T')[0]; // Format YYYY-MM-DD
      
      // Générer un nombre aléatoire d'achats par jour (0-5) pour chaque marque
      brands.forEach(brand => {
        const purchaseCount = Math.floor(Math.random() * 6); // 0 à 5 achats
        
        for (let j = 0; j < purchaseCount; j++) {
          sampleData.push({
            date_achat: dateStr,
            magasin: brand,
            montant_total: Math.random() * 100 + 10 // Montant entre 10 et 110€
          });
        }
      });
    }
    
    return sampleData;
  };
  
  // Fonction pour calculer la disposition en semaines du calendrier
  const calculateCalendarLayout = (dates, counts) => {
    if (!dates || !dates.length) return { z: [], x: [], y: [] };
    
    // Créer un mapping date -> valeur
    const dateValueMap = {};
    dates.forEach((date, index) => {
      dateValueMap[date] = counts[index];
    });
    
    // Déterminer la plage de dates
    const sortedDates = [...dates].sort();
    const startDate = new Date(sortedDates[0]);
    const endDate = new Date(sortedDates[sortedDates.length - 1]);
    
    // Trouver le premier jour de la semaine pour la date de début
    const firstDay = new Date(startDate);
    firstDay.setDate(firstDay.getDate() - firstDay.getDay()); // Reculer jusqu'au dimanche
    
    // Trouver le dernier jour de la semaine pour la date de fin
    const lastDay = new Date(endDate);
    const daysToAdd = 6 - lastDay.getDay();
    lastDay.setDate(lastDay.getDate() + daysToAdd); // Avancer jusqu'au samedi
    
    // Créer une matrice pour la heatmap
    const weekdays = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
    const z = []; // Valeurs de la heatmap
    const x = []; // Jours de la semaine
    const y = []; // Semaines
    
    let currentDate = new Date(firstDay);
    let weekIndex = 0;
    
    while (currentDate <= lastDay) {
      const row = [];
      const xLabels = [];
      
      for (let dayOfWeek = 0; dayOfWeek < 7; dayOfWeek++) {
        const dateStr = currentDate.toISOString().split('T')[0];
        xLabels.push(weekdays[dayOfWeek]);
        
        // Si la date est dans notre ensemble de données, utiliser la valeur, sinon 0
        const value = dateValueMap[dateStr] || 0;
        row.push(value);
        
        // Passer au jour suivant
        currentDate.setDate(currentDate.getDate() + 1);
      }
      
      z.push(row);
      x.push(...xLabels);
      y.push(`Semaine ${weekIndex + 1}`);
      weekIndex++;
    }
    
    return { z, x: weekdays, y };
  };

  // Préparation des données pour le graphique
  const calendarData = data ? formatCalendarData(data, selectedBrand) : null;
  const { z, x, y } = calendarData ? calculateCalendarLayout(calendarData.dates, calendarData.counts) : { z: [], x: [], y: [] };
  
  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <CardTitle className="text-xl font-bold">Calendrier des Achats</CardTitle>
        <div className="flex items-center space-x-4">
          <label htmlFor="brand-select" className="text-sm font-medium">
            Marque:
          </label>
          <select
            id="brand-select"
            className="rounded border border-gray-300 p-1 text-sm"
            value={selectedBrand}
            onChange={(e) => setSelectedBrand(e.target.value)}
          >
            {brands.map((brand) => (
              <option key={brand} value={brand}>
                {brand === 'all' ? 'Toutes les marques' : brand}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="text-primary">Chargement...</div>
          </div>
        ) : error ? (
          <div className="flex h-64 items-center justify-center">
            <div className="text-red-500">{error}</div>
          </div>
        ) : (
          <div className="h-96">
            <Plot
              data={[
                {
                  z: z,
                  x: x,
                  y: y,
                  type: 'heatmap',
                  colorscale: 'Blues',
                  showscale: true,
                  hovertemplate: 'Achats: %{z}<extra></extra>'
                }
              ]}
              layout={{
                title: `Nombre d'achats par jour - ${selectedBrand === 'all' ? 'Toutes marques' : selectedBrand}`,
                height: 380,
                margin: { l: 80, r: 20, b: 30, t: 40, pad: 0 },
                xaxis: {
                  title: 'Jour de la semaine'
                },
                yaxis: {
                  title: 'Semaine',
                  autorange: 'reversed' // Pour afficher les semaines les plus récentes en haut
                }
              }}
              config={{
                responsive: true,
                displayModeBar: false
              }}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DayPlotCalendar;