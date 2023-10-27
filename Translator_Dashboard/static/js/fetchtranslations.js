let currentIndex = 0;

function fetchTranslation(index, dir) {
    fetch(`${CONFIG.API_ENDPOINT}/get-final?direction=${dir}&id=${index}`)
        .then(response => {
            if (response.status === 400) {
                throw new Error('400: Bad Request');
            } else if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Unknown error occurred');
                });
            }
            return response.json(); 
        })
        .then(data => {
            document.getElementById('title').innerText = data.text.title;
            document.getElementById('text').innerText = data.text.text;
            currentIndex = data.id;  
            document.getElementById('currentIndexInput').value = currentIndex;
        })
        .catch(error => {
            console.error('Error fetching translation:', error);
            
            // Check if the error message is a 400 Bad Request
            if (error.message.includes("400: Bad Request")) {
                // Create and display flash message
                var flashMessage = document.createElement('div');
                flashMessage.className = 'flash-message';
                flashMessage.textContent = 'No more translations';
                
                document.body.appendChild(flashMessage);
                
                setTimeout(function() {
                    flashMessage.parentNode.removeChild(flashMessage);
                }, 4000);
            }
        });
}


window.onload = function() {
    // Retrieve buttons by their IDs
    const nextButton = document.getElementById('next-button');
    const prevButton = document.getElementById('prev-button');

    // Event listeners for the buttons
    if (nextButton) {
        nextButton.addEventListener('click', function() {
            fetchTranslation(currentIndex, 'next');
        });
    }
    
    if (prevButton) {
        prevButton.addEventListener('click', function() {
            fetchTranslation(currentIndex, 'prev');
        });
    }

    fetchTranslation(currentIndex, 'next');
};

