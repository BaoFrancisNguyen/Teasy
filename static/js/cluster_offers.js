// JavaScript pour gérer les offres par clusters
document.addEventListener('DOMContentLoaded', function() {
    // Gestion des types d'offre (manuelle vs générée)
    const offerTypeSelects = document.querySelectorAll('.offer-type-select');
    offerTypeSelects.forEach(select => {
        select.addEventListener('change', function() {
            const clusterId = this.id.split('-').pop();
            const manualOptions = document.getElementById(`manual-options-${clusterId}`);
            const generatedOptions = document.getElementById(`generated-options-${clusterId}`);
            
            if (this.value === 'manual') {
                manualOptions.style.display = 'block';
                generatedOptions.style.display = 'none';
            } else {
                manualOptions.style.display = 'none';
                generatedOptions.style.display = 'block';
            }
        });
    });
    
    // Gestion des types d'action
    const actionTypeSelects = document.querySelectorAll('.action-type-select');
    actionTypeSelects.forEach(select => {
        select.addEventListener('change', function() {
            const clusterId = this.id.split('-').pop();
            const valueField = document.querySelector(`#action-value-${clusterId}`).closest('.value-field');
            const giftField = document.querySelector(`#gift-id-${clusterId}`).closest('.gift-field');
            const valueSuffix = document.getElementById(`value-suffix-${clusterId}`);
            
            // Réinitialiser les champs
            valueField.style.display = 'block';
            giftField.style.display = 'none';
            
            // Ajuster selon le type d'action
            switch(this.value) {
                case 'offre_points':
                    valueSuffix.textContent = 'points';
                    break;
                case 'reduction_pourcentage':
                    valueSuffix.textContent = '%';
                    break;
                case 'reduction_montant':
                    valueSuffix.textContent = '€';
                    break;
                case 'offre_cadeau':
                    valueField.style.display = 'none';
                    giftField.style.display = 'block';
                    break;
                case 'notification':
                    valueSuffix.textContent = '';
                    break;
            }
        });
    });
    
    // Initialiser les suffixes de valeur
    actionTypeSelects.forEach(select => {
        const event = new Event('change');
        select.dispatchEvent(event);
    });
    
    // Boutons de génération de suggestion
    const generateButtons = document.querySelectorAll('.generate-suggestion-btn');
    generateButtons.forEach(button => {
        button.addEventListener('click', function() {
            const clusterId = this.dataset.clusterId;
            const contextElement = document.getElementById(`generation-context-${clusterId}`);
            const resultElement = document.getElementById(`suggestion-result-${clusterId}`);
            
            // Afficher un indicateur de chargement
            resultElement.innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"></div> Génération en cours...';
            resultElement.style.display = 'block';
            
            // Récupérer les caractéristiques du cluster
            const clusterStats = {};
            const statElements = this.closest('.accordion-body').querySelectorAll('.cluster-stats .mb-1');
            statElements.forEach(stat => {
                const text = stat.textContent.trim();
                const parts = text.split(':');
                if (parts.length > 1) {
                    const feature = parts[0].trim();
                    const values = parts[1].trim();
                    clusterStats[feature] = values;
                }
            });
            
            // Faire une requête à l'API
            fetch('/api/generate_cluster_offer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    cluster_id: clusterId,
                    cluster_stats: clusterStats,
                    context: contextElement.value
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Afficher la suggestion
                    resultElement.innerHTML = `
                        <div class="alert alert-success">
                            <h6>Suggestion d'offre:</h6>
                            <p>${data.offer_description}</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <span class="badge bg-primary">${data.offer_type}</span>
                                    <span class="badge bg-secondary">${data.offer_value}</span>
                                </div>
                                <button type="button" class="btn btn-sm btn-outline-primary apply-suggestion-btn">
                                    Appliquer
                                </button>
                            </div>
                        </div>
                    `;
                    
                    // Ajouter un gestionnaire pour le bouton d'application
                    resultElement.querySelector('.apply-suggestion-btn').addEventListener('click', function() {
                        // Basculer vers le mode manuel
                        const offerTypeSelect = document.getElementById(`offer-type-${clusterId}`);
                        offerTypeSelect.value = 'manual';
                        offerTypeSelect.dispatchEvent(new Event('change'));
                        
                        // Appliquer les valeurs suggérées
                        const actionTypeSelect = document.getElementById(`action-type-${clusterId}`);
                        actionTypeSelect.value = data.offer_type;
                        actionTypeSelect.dispatchEvent(new Event('change'));
                        
                        document.getElementById(`action-value-${clusterId}`).value = data.offer_value;
                        document.getElementById(`offer-message-${clusterId}`).value = data.offer_message || '';
                    });
                } else {
                    // Afficher l'erreur
                    resultElement.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>
                            Erreur lors de la génération: ${data.error || 'Une erreur est survenue'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                resultElement.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        Erreur de communication avec le serveur: ${error.message}
                    </div>
                `;
            });
        });
    });
    
    // Bouton de prévisualisation des offres
    const previewButton = document.getElementById('preview-offers-btn');
    if (previewButton) {
        previewButton.addEventListener('click', function() {
            const offerForm = document.getElementById('cluster-offers-form');
            const formData = new FormData(offerForm);
            const previewContent = document.getElementById('offers-preview-content');
            
            // Afficher un indicateur de chargement
            previewContent.innerHTML = `
                <div class="text-center p-4">
                    <div class="spinner-border text-primary" role="status"></div>
                    <p class="mt-2">Génération de la prévisualisation...</p>
                </div>
            `;
            
            // Afficher la modale
            const previewModal = new bootstrap.Modal(document.getElementById('previewOffersModal'));
            previewModal.show();
            
            // Faire une requête à l'API pour obtenir la prévisualisation
            fetch('/api/preview_cluster_offers', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Construire le contenu de prévisualisation
                    let html = '<div class="offers-preview">';
                    
                    data.offers.forEach(offer => {
                        // Déterminer l'icône en fonction du type d'offre
                        let icon, badgeClass;
                        switch (offer.action_type) {
                            case 'offre_points':
                                icon = 'star';
                                badgeClass = 'bg-primary';
                                break;
                            case 'reduction_pourcentage':
                                icon = 'percent';
                                badgeClass = 'bg-success';
                                break;
                            case 'reduction_montant':
                                icon = 'currency-euro';
                                badgeClass = 'bg-info';
                                break;
                            case 'offre_cadeau':
                                icon = 'gift';
                                badgeClass = 'bg-warning';
                                break;
                            case 'notification':
                                icon = 'bell';
                                badgeClass = 'bg-secondary';
                                break;
                            default:
                                icon = 'tag';
                                badgeClass = 'bg-dark';
                        }
                        
                        html += `
                            <div class="card mb-3">
                                <div class="card-header bg-light">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <strong>Cluster ${offer.cluster_id}</strong>
                                        <span class="badge ${badgeClass}">
                                            <i class="bi bi-${icon} me-1"></i> 
                                            ${offer.action_type_label}
                                        </span>
                                    </div>
                                </div>
                                <div class="card-body">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <h6>Détails de l'offre:</h6>
                                            <p>${offer.description}</p>
                                            <div>
                                                <strong>Valeur:</strong> ${offer.action_value}
                                            </div>
                                            ${offer.message ? `<div class="mt-2"><strong>Message:</strong> ${offer.message}</div>` : ''}
                                        </div>
                                        <div class="col-md-6">
                                            <h6>Impact:</h6>
                                            <div><strong>Clients ciblés:</strong> ${offer.clients_count}</div>
                                            <div><strong>Coût estimé:</strong> ${offer.estimated_cost}</div>
                                            <div><strong>Date d'expiration:</strong> ${offer.expiration_date}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                    previewContent.innerHTML = html;
                } else {
                    // Afficher l'erreur
                    previewContent.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>
                            ${data.error || 'Une erreur est survenue lors de la prévisualisation'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                previewContent.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        Erreur de communication avec le serveur: ${error.message}
                    </div>
                `;
            });
        });
    }
    
    // Bouton de confirmation des offres
    const confirmButton = document.getElementById('confirm-offers-btn');
    if (confirmButton) {
        confirmButton.addEventListener('click', function() {
            document.getElementById('cluster-offers-form').submit();
        });
    }
});
