
let currentIndex = 1; 

function getProviderColumns(provider) {
    switch (provider) {
        case 'aws':
            return ['aws_title', 'aws_text', 'aws_checksum', 'first_translation'];
        case 'gcp':
            return ['gcp_title', 'gcp_text', 'gcp_checksum', 'first_translation'];
        case 'azure':
            return ['azure_title', 'azure_text', 'azure_checksum', 'first_translation'];
        default:
            return [];
    }
}

function fetchTranslationForService(service) {
    let columns = getProviderColumns(service);
    const [titleColumn, textColumn, checksumColumn, table] = columns;

    return fetch(`${CONFIG.API_ENDPOINT}/get-translation?title_column=${titleColumn}&text_column=${textColumn}&checksum_column=${checksumColumn}&table=${table}&direction=next&id=${currentIndex}`)
        .then(response => response.json());
}


function fetchOriginalArticle(id) {
    fetch(`${CONFIG.API_ENDPOINT}/get-article?id=${id}`)
        .then(response => response.json())
        .then(data => {
            const originalArticleTextarea = document.getElementById('originalArticle');
            originalArticleTextarea.value = data.title + "\n\n" + data.text;
        });
}

function updateTranslationElements() {
    let promises = [];

    // AWS
    promises.push(fetchTranslationForService('aws')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const awsTextarea = document.getElementById('awsTranslation');
                if (awsTextarea) awsTextarea.value = data.title + "\n\n" + data.text;
            }
            return data;
        }));

    // Google Cloud
    promises.push(fetchTranslationForService('gcp')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const gcpTextarea = document.getElementById('googleTranslation');
                if (gcpTextarea) gcpTextarea.value = data.title + "\n\n" + data.text;
            }
            return data;
        }));

    // Microsoft Azure
    promises.push(fetchTranslationForService('azure')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const azureTextarea = document.getElementById('azureTranslation');
                if (azureTextarea) azureTextarea.value = data.title + "\n\n" + data.text;
            }
            return data;
        }));

    // When all translations have been fetched
    Promise.all(promises).then(results => {
        let nonEmptyResult = results.find(data => Object.keys(data).length !== 0);
    
        if (nonEmptyResult) {
            currentIndex = nonEmptyResult.id;
            fetchOriginalArticle(currentIndex);
        }
    });
}

// Event listener for 'Next Article' button
// Using jQuery to select the button and attach an event
$('.custom-button:contains("Next Article")').click(function() {
    updateTranslationElements();
});

// Initialize when the document is ready
$(document).ready(function() {
    updateTranslationElements();
});

