const downloadWordDoc = () => {
    let fullContent; // Define fullContent outside of the if scope

    const titleBlock = document.getElementById("title");
    const contentBlock = document.getElementById("text");

    // Check if BOTH titleBlock and contentBlock exist
    if (titleBlock && contentBlock) {
        const title = titleBlock.innerText; // Use .innerText to get the visible text content
        const content = contentBlock.innerText;

        // Combine the title and content with a newline in between
        fullContent = title + "\n\n" + content;
    } else {
        // If title and text don't exist, use the content from baseTranslation
        const baseContentBlock = document.getElementById("baseTranslation");
        fullContent = baseContentBlock.value; // Use .value to get the text content
    }

    // Create a Blob with content and specify the MIME type for a Word document
    const file = new Blob([fullContent], { type: 'application/msword' });

    // Create an anchor element to trigger the download
    const link = document.createElement("a");
    link.href = URL.createObjectURL(file);
    link.download = "document.doc"; // Specify the desired file name
    link.click();

    // Clean up resources
    URL.revokeObjectURL(link.href);
};

