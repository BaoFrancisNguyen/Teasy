document.addEventListener('DOMContentLoaded', function() {
    // Sélecteurs des éléments du DOM
    const dayPlotCalendar = document.getElementById('day-plot-calendar');
    const brandSelect = document.getElementById('brand-select');
    const paymentMethodSelect = document.getElementById('payment-method-select');
    const genderSelect = document.getElementById('gender-select');
    const ageRangeSelect = document.getElementById('age-range-select');
    const articleSelect = document.getElementById('article-select');
    const dateStart = document.getElementById('date-start');
    const dateEnd = document.getElementById('date-end');
    const applyFiltersBtn = document.getElementById('apply-filters');
    const loadingIndicator = document.getElementById('loading-indicator');
    const errorMessage = document.getElementById('error-message');
    const filterInfo = document.getElementById('filter-info');
    const activeFilters = document.getElementById('active-filters');

    // Initialiser les dates par défaut (3 derniers mois)
    const today = new Date();
    dateEnd.valueAsDate = today;
    
    const threeMonthsAgo = new Date();
    threeMonthsAgo.setMonth(today.getMonth() - 3);
    dateStart.valueAsDate = threeMonthsAgo;

    // Fonction pour charger les données du calendrier
    async function loadCalendarData() {
        try {
            // Afficher l'indicateur de chargement
            loadingIndicator.style.display = 'block';
            dayPlotCalendar.style.display = 'none';
            errorMessage.style.display = 'none';
            filterInfo.style.display = 'none';

            // Récupérer les filtres directement depuis les éléments DOM
            const filters = {
                brand: brandSelect.value || 'all',
                payment_method: paymentMethodSelect.value || 'all',
                gender: genderSelect.value || 'all',
                age_range: ageRangeSelect.value || 'all',
                article: articleSelect.value || 'all',
                date_start: dateStart.value || null,
                date_end: dateEnd.value || null
            };
            
            console.log("Filtres envoyés à l'API:", filters);
            console.log("Valeur du select genre:", genderSelect.value);
            console.log("Option genre sélectionnée:", genderSelect.options[genderSelect.selectedIndex].text);
            console.log("Valeur du select âge:", ageRangeSelect.value);

            // Requête AJAX pour obtenir les données
            const response = await fetch('/api/calendar_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(filters)
            });

            const data = await response.json();
            console.log("Données reçues de l'API:", data);

            if (!data.success) {
                throw new Error(data.error || 'Erreur lors du chargement des données');
            }

            // Mettre à jour les listes de sélection si des données sont disponibles
            if (data.payment_methods && data.payment_methods.length > 0) {
                console.log("Mise à jour du sélecteur de moyens de paiement avec:", data.payment_methods);
                updateSelectOptions(paymentMethodSelect, data.payment_methods, 'all', 'Tous les moyens');
            }
            
            if (data.articles && data.articles.length > 0) {
                console.log("Mise à jour du sélecteur d'articles avec:", data.articles);
                updateSelectOptions(articleSelect, data.articles, 'all', 'Tous les articles');
            }
            
            if (data.brands && data.brands.length > 0) {
                updateSelectOptions(brandSelect, data.brands, 'all', 'Tous les magasins');
            }

            // Afficher les filtres actifs
            displayActiveFilters(filters);

            // Si aucune donnée n'est disponible
            if (!data.dates || data.dates.length === 0) {
                errorMessage.textContent = 'Aucune donnée disponible pour cette sélection';
                errorMessage.style.display = 'block';
                loadingIndicator.style.display = 'none';
                return;
            }

            // Préparer les données pour le calendrier
            const calendarData = data.dates.map((date, index) => ({
                date: date,
                value: data.values[index] || 0,
                paymentInfo: data.paymentInfo ? data.paymentInfo[index] : null,
                magasin: data.magasins ? data.magasins[index] : null,
                gender: data.genders ? data.genders[index] : null,
                age: data.ages ? data.ages[index] : null
            }));

            // Créer une structure de données de type calendrier (regroupement par semaine/jour)
            const weeks = {};
            const days = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
            
            // Agréger les données par date
            const dateMap = {};
            calendarData.forEach(item => {
                if (!dateMap[item.date]) {
                    dateMap[item.date] = {
                        date: item.date,
                        value: item.value,
                        details: []
                    };
                } else {
                    dateMap[item.date].value += item.value;
                }
                
                // Ajouter les informations détaillées
                dateMap[item.date].details.push({
                    paymentInfo: item.paymentInfo,
                    magasin: item.magasin,
                    gender: item.gender,
                    age: item.age,
                    value: item.value
                });
            });
            
            // Structurer les données par semaine pour l'affichage du calendrier
            Object.values(dateMap).forEach(item => {
                const date = new Date(item.date);
                const dayOfWeek = date.getDay(); // 0 = Dimanche, 6 = Samedi
                
                // Trouver le lundi de la semaine
                const mondayDate = new Date(date);
                mondayDate.setDate(date.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1)); // Si dimanche, reculer d'une semaine
                
                const weekKey = mondayDate.toISOString().split('T')[0];
                
                if (!weeks[weekKey]) {
                    weeks[weekKey] = Array(7).fill(null).map(() => ({ value: 0, details: [], date: null }));
                }
                
                // Mettre à jour la valeur pour ce jour de la semaine
                const dayIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
                weeks[weekKey][dayIndex].value = item.value;
                weeks[weekKey][dayIndex].details = item.details;
                weeks[weekKey][dayIndex].date = item.date;
            });

            // Trier les semaines par ordre chronologique
            const weekKeys = Object.keys(weeks).sort();
            const sortedWeeks = weekKeys.map(key => weeks[key]);
            
            // Convertir en format adapté pour Plotly
            const z = sortedWeeks.map(week => week.map(day => day.value || 0));
            const text = sortedWeeks.map(week => 
                week.map(day => {
                    if (!day.date) return "Pas de données";
                    if (!day.details || day.details.length === 0) return `Date: ${day.date}<br>Pas d'achats`;
                    
                    // Regrouper par différents critères
                    const paymentSummary = {};
                    const storeSummary = {};
                    const genderSummary = {};
                    const ageSummary = {};
                    
                    day.details.forEach(detail => {
                        if (detail.paymentInfo) {
                            paymentSummary[detail.paymentInfo] = (paymentSummary[detail.paymentInfo] || 0) + detail.value;
                        }
                        if (detail.magasin) {
                            storeSummary[detail.magasin] = (storeSummary[detail.magasin] || 0) + detail.value;
                        }
                        if (detail.gender) {
                            genderSummary[detail.gender] = (genderSummary[detail.gender] || 0) + detail.value;
                        }
                        if (detail.age) {
                            let ageGroup = '';
                            const age = Number(detail.age);
                            if (age < 19) ageGroup = '0-18 ans';
                            else if (age <= 25) ageGroup = '19-25 ans';
                            else if (age <= 35) ageGroup = '26-35 ans';
                            else if (age <= 50) ageGroup = '36-50 ans';
                            else ageGroup = '51+ ans';
                            
                            ageSummary[ageGroup] = (ageSummary[ageGroup] || 0) + detail.value;
                        }
                    });
                    
                    // Construire le texte d'info-bulle
                    let tooltip = `<b>Date</b>: ${day.date}<br><b>Total</b>: ${day.value} achat(s)<br>`;
                    
                    if (Object.keys(paymentSummary).length > 0) {
                        tooltip += "<br><b>Moyens de paiement</b>:<br>";
                        Object.entries(paymentSummary).forEach(([method, count]) => {
                            tooltip += `- ${method}: ${count} achat(s)<br>`;
                        });
                    }
                    
                    if (Object.keys(storeSummary).length > 0 && filters.brand === 'all') {
                        tooltip += "<br><b>Magasins</b>:<br>";
                        Object.entries(storeSummary).forEach(([store, count]) => {
                            tooltip += `- ${store}: ${count} achat(s)<br>`;
                        });
                    }
                    
                    if (Object.keys(genderSummary).length > 0 && filters.gender === 'all') {
                        tooltip += "<br><b>Répartition par genre</b>:<br>";
                        Object.entries(genderSummary).forEach(([gender, count]) => {
                            tooltip += `- ${gender}: ${count} achat(s)<br>`;
                        });
                    }
                    
                    if (Object.keys(ageSummary).length > 0 && filters.age_range === 'all') {
                        tooltip += "<br><b>Répartition par âge</b>:<br>";
                        Object.entries(ageSummary).forEach(([ageGroup, count]) => {
                            tooltip += `- ${ageGroup}: ${count} achat(s)<br>`;
                        });
                    }
                    
                    return tooltip;
                })
            );
            
            const x = days;
            const y = weekKeys.map(week => {
                const date = new Date(week);
                return `Semaine du ${date.getDate()}/${date.getMonth() + 1}`;
            });

            // Calculer le titre en fonction des filtres
            let titleText = 'Calendrier des Achats';
            const filterTexts = [];
            
            if (filters.brand !== 'all') {
                filterTexts.push(`Magasin: ${brandSelect.options[brandSelect.selectedIndex].text}`);
            }
            
            if (filters.payment_method !== 'all') {
                filterTexts.push(`Paiement: ${paymentMethodSelect.options[paymentMethodSelect.selectedIndex].text}`);
            }
            
            if (filters.gender !== 'all') {
                filterTexts.push(`Genre: ${genderSelect.options[genderSelect.selectedIndex].text}`);
            }
            
            if (filters.age_range !== 'all') {
                filterTexts.push(`Âge: ${ageRangeSelect.options[ageRangeSelect.selectedIndex].text}`);
            }
            
            if (filters.article !== 'all') {
                const articleText = articleSelect.options[articleSelect.selectedIndex] ? 
                                   articleSelect.options[articleSelect.selectedIndex].text : 
                                   filters.article;
                filterTexts.push(`Article: ${articleText}`);
            }
            
            if (filterTexts.length > 0) {
                titleText += ` (${filterTexts.join(', ')})`;
            }

            // Créer le tracé de calendrier
            const plotData = [{
                z: z,
                x: x,
                y: y,
                type: 'heatmap',
                // Couleurs inversées de bleu clair à bleu foncé
                colorscale: [
                    [0, 'rgb(247, 251, 255)'],   // Très clair (valeurs faibles)
                    [0.2, 'rgb(198, 219, 239)'], 
                    [0.4, 'rgb(158, 202, 225)'],
                    [0.6, 'rgb(107, 174, 214)'],
                    [0.8, 'rgb(49, 130, 189)'],
                    [1, 'rgb(8, 48, 107)']       // Très foncé (valeurs élevées)
                ],
                showscale: true,
                hoverongaps: false,
                text: text,
                hoverinfo: 'text',
                colorbar: {
                    title: 'Nombre d\'achats',
                    titlefont: {
                        size: 14
                    }
                }
            }];

            const layout = {
                title: {
                    text: titleText,
                    font: {
                        size: 18
                    }
                },
                // Hauteur augmentée à 600px
                height: 600,
                margin: {
                    l: 150, // Plus de marge à gauche pour les labels de semaine
                    r: 50,
                    t: 70,  // Plus de marge en haut pour le titre
                    b: 50
                },
                // Personnalisation des axes
                xaxis: {
                    title: 'Jour de la semaine',
                    titlefont: {
                        size: 14
                    }
                },
                yaxis: {
                    title: 'Semaine',
                    titlefont: {
                        size: 14
                    },
                    // Afficher les semaines les plus récentes en haut
                    autorange: 'reversed'
                }
            };

            const config = {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: [
                    'lasso2d', 'select2d', 'toggleSpikelines'
                ],
                displaylogo: false,
                toImageButtonOptions: {
                    format: 'png',
                    filename: 'calendrier_achats',
                    height: 600,
                    width: 1200,
                    scale: 2
                }
            };

            // Créer le graphique
            Plotly.newPlot('day-plot-calendar', plotData, layout, config);

            // Cacher le spinner de chargement
            loadingIndicator.style.display = 'none';
            dayPlotCalendar.style.display = 'block';

        } catch (error) {
            console.error('Erreur lors du chargement des données:', error);
            loadingIndicator.style.display = 'none';
            errorMessage.textContent = error.message || 'Une erreur s\'est produite lors du chargement des données.';
            errorMessage.style.display = 'block';
        }
    }

    // Fonction pour mettre à jour les options d'un select
    function updateSelectOptions(selectElement, options, defaultValue, defaultText) {
        if (!selectElement) {
            console.error("Élément select non trouvé");
            return;
        }
        
        // Conserver la valeur actuelle avant la mise à jour
        const currentValue = selectElement.value;
        
        // Vider la liste
        selectElement.innerHTML = '';
        
        // Ajouter l'option par défaut
        const newDefaultOption = document.createElement('option');
        newDefaultOption.value = defaultValue;
        newDefaultOption.textContent = defaultText;
        selectElement.appendChild(newDefaultOption);
        
        // Ajouter les nouvelles options
        options.forEach(option => {
            if (option) { // Vérifier que l'option n'est pas nulle
                const optionElement = document.createElement('option');
                optionElement.value = option;
                optionElement.textContent = option;
                selectElement.appendChild(optionElement);
            }
        });
        
        // Essayer de restaurer la valeur précédente si possible
        if (currentValue !== defaultValue) {
            const exists = Array.from(selectElement.options).some(option => option.value === currentValue);
            if (exists) {
                selectElement.value = currentValue;
            } else {
                selectElement.value = defaultValue;
            }
        }
    }
    
    // Fonction pour afficher les filtres actifs
    function displayActiveFilters(filters) {
        // Vérifier si au moins un filtre est actif
        const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
            if (key === 'date_start' || key === 'date_end') {
                return value !== null;
            }
            return value !== 'all';
        });
        
        if (!hasActiveFilters) {
            filterInfo.style.display = 'none';
            return;
        }
        
        // Préparer la liste des filtres actifs
        activeFilters.innerHTML = '';
        
        if (filters.brand !== 'all') {
            const li = document.createElement('li');
            li.textContent = `Magasin : ${brandSelect.options[brandSelect.selectedIndex].text}`;
            activeFilters.appendChild(li);
        }
        
        if (filters.payment_method !== 'all') {
            const li = document.createElement('li');
            li.textContent = `Moyen de paiement : ${paymentMethodSelect.options[paymentMethodSelect.selectedIndex].text}`;
            activeFilters.appendChild(li);
        }
        
        if (filters.gender !== 'all') {
            const li = document.createElement('li');
            li.textContent = `Genre : ${genderSelect.options[genderSelect.selectedIndex].text}`;
            activeFilters.appendChild(li);
        }
        
        if (filters.age_range !== 'all') {
            const li = document.createElement('li');
            li.textContent = `Tranche d'âge : ${ageRangeSelect.options[ageRangeSelect.selectedIndex].text}`;
            activeFilters.appendChild(li);
        }
        
        if (filters.article !== 'all') {
            const li = document.createElement('li');
            const articleText = articleSelect.options[articleSelect.selectedIndex] ? 
                               articleSelect.options[articleSelect.selectedIndex].text : 
                               filters.article;
            li.textContent = `Article : ${articleText}`;
            activeFilters.appendChild(li);
        }
        
        if (filters.date_start) {
            const li = document.createElement('li');
            li.textContent = `Date de début : ${new Date(filters.date_start).toLocaleDateString()}`;
            activeFilters.appendChild(li);
        }
        
        if (filters.date_end) {
            const li = document.createElement('li');
            li.textContent = `Date de fin : ${new Date(filters.date_end).toLocaleDateString()}`;
            activeFilters.appendChild(li);
        }
        
        filterInfo.style.display = 'block';
    }
    
    // Charger les données initiales
    loadCalendarData();

    // Gestionnaire d'événements pour le bouton d'application des filtres
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', loadCalendarData);
    }

    // Ajouter un gestionnaire pour le redimensionnement
    window.addEventListener('resize', function() {
        if (dayPlotCalendar.style.display !== 'none') {
            Plotly.relayout('day-plot-calendar', {
                width: dayPlotCalendar.offsetWidth
            });
        }
    });
    
    // Ajouter des gestionnaires pour les sélecteurs (pour l'UI uniquement, le chargement se fait avec le bouton)
    const selectors = [brandSelect, paymentMethodSelect, genderSelect, ageRangeSelect, articleSelect, dateStart, dateEnd];
    selectors.forEach(selector => {
        if (selector) {
            selector.addEventListener('change', function() {
                // Mettre à jour visuellement que le bouton doit être cliqué
                applyFiltersBtn.classList.add('btn-pulse');
                setTimeout(() => {
                    applyFiltersBtn.classList.remove('btn-pulse');
                }, 1000);
            });
        }
    });
});

// Ajouter ce code au fichier static/js/day-plot-calendar.js

// Sélection des éléments DOM pour les filtres client
const genderSelect = document.getElementById('gender-select');
const ageRangeSelect = document.getElementById('age-range-select');

// État des filtres - ajouter les filtres client
let filters = {
  brand: 'all',
  payment_method: 'all',
  article: 'all',
  gender: 'all',
  age_range: 'all'
};

// Mettre à jour la fonction loadDayPlotData pour inclure les filtres client
function loadDayPlotData() {
  // Afficher l'indicateur de chargement
  loadingIndicator.style.display = 'block';
  dayPlotCalendar.style.display = 'none';
  errorMessage.style.display = 'none';

  // Récupérer les données du calendrier avec les filtres
  fetch('/api/calendar_data', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(filters)
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      // Mettre à jour les listes déroulantes des filtres
      updateFilterDropdowns(data);
      
      // Créer le calendrier avec les données
      createDayPlotCalendar(data.dates, data.values);
      
      // Masquer l'indicateur de chargement et afficher le graphique
      loadingIndicator.style.display = 'none';
      dayPlotCalendar.style.display = 'block';
    } else {
      console.error('Erreur:', data.error);
      showError(data.error || 'Erreur lors du chargement des données');
    }
  })
  .catch(error => {
    console.error('Erreur de fetch:', error);
    showError('Erreur de communication avec le serveur');
  });
}

// Mettre à jour la fonction updateFilterDropdowns
function updateFilterDropdowns(data) {
  // Mise à jour des listes déroulantes existantes
  updateBrandDropdown(data.brands);
  updatePaymentMethodDropdown(data.payment_methods);
  
  // Mise à jour des listes déroulantes pour les filtres client
  if (genderSelect && data.available_genders) {
    // Sauvegarder la valeur actuellement sélectionnée
    const currentSelection = genderSelect.value;
    
    // Vider le sélecteur
    genderSelect.innerHTML = '<option value="all">Tous les genres</option>';
    
    // Ajouter les options de genre disponibles
    data.available_genders.forEach(gender => {
      const option = document.createElement('option');
      option.value = gender.toLowerCase();
      option.textContent = gender.charAt(0).toUpperCase() + gender.slice(1).toLowerCase();
      genderSelect.appendChild(option);
    });
    
    // Restaurer la sélection ou utiliser 'all' par défaut
    genderSelect.value = currentSelection;
  }
  
  // Age range est déjà statique, pas besoin de le mettre à jour dynamiquement
}

// Ajouter des écouteurs d'événements pour les filtres client
if (genderSelect) {
  genderSelect.addEventListener('change', function() {
    filters.gender = this.value;
    loadDayPlotData();
  });
}

if (ageRangeSelect) {
  ageRangeSelect.addEventListener('change', function() {
    filters.age_range = this.value;
    loadDayPlotData();
  });
}