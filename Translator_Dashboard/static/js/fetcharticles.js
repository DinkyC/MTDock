
let currentIndex = 0; 

function getProviderColumns(provider) {
    switch (provider) {
        case 'aws':
            return 1;
        case 'gcp':
            return 2;
        case 'azure':
            return 3;
        default:
            return [];
    }
}

function fetchTranslationForService(service) {
    let to_lang = document.getElementById("translateTo")
    let providers_id = getProviderColumns(service);
    let fetchUrl = `${CONFIG.API_ENDPOINT}/get-first?providers_id=${providers_id}&direction=next&to_lang=${to_lang.value}&id=${currentIndex}`;
    return fetch(fetchUrl)
        .then(response => {

            return response.json();
        });
}

function fetchTranslationForServicePrev(service) {
    let to_lang = document.getElementById("translateTo")
    let providers_id = getProviderColumns(service);
    let fetchUrl = `${CONFIG.API_ENDPOINT}/get-first?providers_id=${providers_id}&direction=prev&to_lang=${to_lang.value}&id=${currentIndex}`;
    return fetch(fetchUrl)
        .then(response => {
            if (!response.ok && response.status === 400) {
                showFlashMessage("No more articles");
            }
            return response.json();
        });
}

function showFlashMessage(message) {
    // Create and display flash message
    var flashMessage = document.createElement('div');
    flashMessage.className = 'flash-message';
    flashMessage.textContent = message;
    document.body.appendChild(flashMessage);
    
    setTimeout(function() {
        flashMessage.parentNode.removeChild(flashMessage);
    }, 4000);
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
                if (awsTextarea) awsTextarea.value = data.text.title + "\n\n" + data.text.text;
            }
            return data;
        }));

    // Google Cloud
    promises.push(fetchTranslationForService('gcp')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const gcpTextarea = document.getElementById('googleTranslation');
                if (gcpTextarea) gcpTextarea.value = data.text.title + "\n\n" + data.text.text;
            }
            return data;
        }));

    // Microsoft Azure
    promises.push(fetchTranslationForService('azure')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const azureTextarea = document.getElementById('azureTranslation');
                if (azureTextarea) azureTextarea.value = data.text.title + "\n\n" + data.text.text;
            }
            return data;
        }));
    const initialIndex = currentIndex;
    // When all translations have been fetched
    Promise.all(promises).then(results => {
        let nonEmptyResult = results.find(data => Object.keys(data).length !== 0);
    
        if (nonEmptyResult) {
            currentIndex = nonEmptyResult.id;
            fetchOriginalArticle(currentIndex);
            updateCurrentIndexInput();
        }
        if (initialIndex === currentIndex) {
            showFlashMessage("No more articles");
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
                if (awsTextarea) awsTextarea.value = data.text.title + "\n\n" + data.text.text;
            }
            return data;
        }));

    // Google Cloud
    promises.push(fetchTranslationForServicePrev('gcp')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const gcpTextarea = document.getElementById('googleTranslation');
                if (gcpTextarea) gcpTextarea.value = data.text.title + "\n\n" + data.text.text;
            }
            return data;
        }));

    // Microsoft Azure
    promises.push(fetchTranslationForServicePrev('azure')
        .then(data => {
            if (Object.keys(data).length !== 0) {
                const azureTextarea = document.getElementById('azureTranslation');
                if (azureTextarea) azureTextarea.value = data.text.title + "\n\n" + data.text.text;
            }
            return data;
        }));
    // When all translations have been fetched
    Promise.all(promises).then(results => {
        let nonEmptyResult = results.find(data => Object.keys(data).length !== 0);
    
        if (nonEmptyResult) {
            currentIndex = nonEmptyResult.id;
            fetchOriginalArticle(currentIndex);
            updateCurrentIndexInput();
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

function setRating(platform, ratingValue) {
    let ratingElementId;
    let inputElementId;

    if (platform === 'GCP') {
        ratingElementId = 'GCP_rating';
        inputElementId = 'GCPRatingInput';
    } else if (platform === 'Azure') {
        ratingElementId = 'Azure_rating';  // Ensure this ID matches the one in your HTML
        inputElementId = 'AzureRatingInput';
    } else if (platform === 'AWS') {
        ratingElementId = 'AWS_rating';  // If you have an element for AWS, set its ID here
        inputElementId = 'AWSRatingInput';
    }

    // Set the value to the appropriate input
    document.getElementById(inputElementId).value = ratingValue;

    // Update the visual representation of stars
    const stars = document.querySelectorAll(`#${ratingElementId} span`);
    stars.forEach((star, index) => {
        if (index < ratingValue) {
            star.classList.add('active');
        } else {
            star.classList.remove('active');
        }
    });
}


document.addEventListener("DOMContentLoaded", function() {
    function addEventListenerForTranslation(buttonId, translationId) {
        let button = document.getElementById(buttonId);
        if (button) {
            console.log("triggered!");
            button.addEventListener('click', function() {
                console.log("clicked");
                copyToBaseTranslation(translationId);
            });
        }
    }

    // Add event listeners for AWS, Google, and Azure translations
    addEventListenerForTranslation('awsButton', 'awsTranslation');
    addEventListenerForTranslation('googleButton', 'googleTranslation');
    addEventListenerForTranslation('azureButton', 'azureTranslation');
});

  function copyToBaseTranslation(id) {
        var content = document.getElementById(id).value;
        var baseTranslation = document.getElementById('baseTranslation');
        baseTranslation.value = content;
        }

document.getElementById('dropdown').addEventListener('change', function() {
    let currentLang = document.getElementById('translateTo');
    if (currentLang) {
        currentLang.value = this.value;
        updateTranslationElements()
    } else {
        console.log("currentLang not found!")
    }
    console.log("Selected value:", this.value);
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

document.addEventListener('DOMContentLoaded', function() {
    let nextButton = document.getElementById('next');
    if (nextButton) {
        nextButton.addEventListener('click', updateTranslationElements);
    }
})

// Event listener for 'Previous Article' button
document.addEventListener('DOMContentLoaded', function() {
    var prevButton = document.querySelector('.custom-button');
    if (prevButton) {
        prevButton.addEventListener('click', updateTranslationElementsPrev);
    }
});


// Initialize when the document is ready
document.addEventListener('DOMContentLoaded', function() {
    let lang_to = document.getElementById("translateTo")
    if (lang_to.value) {
        updateTranslationElements();
    }
});

