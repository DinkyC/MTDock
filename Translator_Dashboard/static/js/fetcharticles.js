
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

function fetchTranslationForServicePrev(service) {
    let columns = getProviderColumns(service);
    const [titleColumn, textColumn, checksumColumn, table] = columns;

    return fetch(`${CONFIG.API_ENDPOINT}/get-translation?title_column=${titleColumn}&text_column=${textColumn}&checksum_column=${checksumColumn}&table=${table}&direction=prev&id=${currentIndex}`)
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
            updateCurrentIndexInput();
            fetchOriginalArticle(currentIndex);
        }
    });
}

function updateTranslationElementsPrev() {
    let promises = [];

    // AWS
    promises.push(fetchTranslationForServicePrev('aws')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const awsTextarea = document.getElementById('awsTranslation');
                if (awsTextarea) awsTextarea.value = data.title + "\n\n" + data.text;
            }
            return data;
        }));

    // Google Cloud
    promises.push(fetchTranslationForServicePrev('gcp')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const gcpTextarea = document.getElementById('googleTranslation');
                if (gcpTextarea) gcpTextarea.value = data.title + "\n\n" + data.text;
            }
            return data;
        }));

    // Microsoft Azure
    promises.push(fetchTranslationForServicePrev('azure')
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
            updateCurrentIndexInput();
            fetchOriginalArticle(currentIndex);
        }
    });
}

function updateCurrentIndexInput() {
    const currentIndexInput = document.getElementById('currentIndexInput');
    if (currentIndexInput) {
        currentIndexInput.value = currentIndex;
        console.log("Updated currentIndex to:", currentIndex);  // Debugging line
    } else {
        console.log("currentIndexInput not found!");  // Debugging line
    }
}

function regenerateTranslation() {
    const currentIndex = document.getElementById('currentIndexInput').value;
    const lang = document.getElementById('translateTo').value;

    if (currentIndex && lang) {
        // Show spinner
        document.getElementById('spinner').style.display = 'block';

        // Introduce a delay of 10 seconds
        setTimeout(() => {
            fetch(`${CONFIG.API_ENDPOINT}/push-to-fifo?id=${currentIndex}&from_lang=en&to_lang=${lang}`, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Network response was not ok");
                }
                return response.text();
            })
            .then(data => {
                updateTranslationElements();
                // Hide spinner
                document.getElementById('spinner').style.display = 'none';
            })
            .catch(error => {
                console.error("There was a problem with the fetch operation:", error.message);
                // Hide spinner
                document.getElementById('spinner').style.display = 'none';
            });
        }, 10000); // 10 seconds delay
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const regenButton = document.getElementById('regenerate');
    if (regenButton) {
        regenButton.addEventListener('click', regenerateTranslation);
    }
});

document.getElementById('dropdown').addEventListener('change', function() {
    const currentLang = document.getElementById('translateTo');
    if (currentLang) {
        currentLang.value = this.value;
    } else {
        console.log("currentLang not found!")
    }
    console.log("Selected value:", this.value);
});

// Event listener for 'Next Article' button
// Using jQuery to select the button and attach an event
$('.custom-button:contains("Next Translation")').click(function() {
    updateTranslationElements();
});

// Event listener for 'Previous Article' button
document.addEventListener('DOMContentLoaded', function() {
    var prevButton = document.querySelector('.custom-button');
    if (prevButton) {
        prevButton.addEventListener('click', updateTranslationElementsPrev);
    }
});


// Initialize when the document is ready
$(document).ready(function() {
    updateTranslationElements();
});

