const downloadWordDoc = () => {
    const baseContentBlock = document.getElementById("baseTranslation");
    const fullContent = baseContentBlock.value;

    const doc = new docx.Document({
        sections: [{
            properties: {},
            children: fullContent.split('\n').map(line => 
                new docx.Paragraph({
                    children: [new docx.TextRun(line)],
                    spacing: {
                        after: 200, // Space after each paragraph, adjust as needed
                    },
                })
            ),
        }],
    });

    // Use Packer to generate a Blob from the document
    docx.Packer.toBlob(doc).then(blob => {
        console.log(blob);
        saveAs(blob, "document.docx");
        console.log("Document created successfully");
    });
};


