# Durable Indexing

Durable Indexing helps you push data to Azure AI Search in a scalable, observable way. Instead of using a pull-based DSL approach (which can be tricky to debug and customize), this solution uses Azure Durable Functions to handle everything from parsing your documents to uploading embeddings—without restarting at every little hiccup.

## Why Push Instead of Pull?
- **Easier Debugging:** No more dealing with hidden logic in a DSL.  
- **Better Control:** You choose how you parse, chunk, and upload your data.  
- **State Management:** Check the status of your indexing run at any time.  

## What’s Inside?
- **Orchestrators and Activities:** Each document gets its own sub-orchestrator, so failures don't bring everything down.  
- **Blob Storage Input:** Drop your PDFs into blob storage, and we’ll automatically pick them up.  
- **Document Intelligence:** Extract text from documents before sending them on.  
- **“Chonkie” for Chunking:** Break down big files into smaller pieces for easier processing.  
- **OpenAI Text-003-Large Embeddings:** Transform your text into embeddings for full-text AI search.  
- **Azure AI Search Upload:** All neatly sent to your search index.  
- **Scalability:** Process documents in parallel without losing track, thanks to continuation tokens and Durable Functions’ built-in retries.

## Getting Started

1. **Prerequisites**  
   - Azure account  
   - [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)  
   - [azd](https://github.com/azure/azure-dev)  
   - Bruno or another tool for using the collection in `/http`  

2. **Deployment**  
   ```bash
   azd up
   ```
   This spins up the infrastructure (storage, function app, AI Search, etc.) and gets you ready to start indexing.

3. **Index Your Documents**  
   - Place your PDFs in the configured blob container.  
   - Kick of the indexing with brung collection in the /http folder (parsing, chunking, embedding, and pushing to search).  

4. **Track Your Runs**  
   - Check the `/http` folder for a Bruno collection with handy endpoints to:
     - **Start** indexing for a specific blob.  
     - **Check** the status of an indexing run.  

## State Management & Scalability
- **Status Monitoring:** Each indexing run is tied to a sub-orchestrator. You can see exactly how far along it is, and if something fails, you can resume without starting over.  
- **Parallel Processing:** Handle as many documents as you want in parallel (just adjust your function settings).  

## Contributing
Feel free to open issues or submit pull requests if you’d like to help out. All improvements are welcome—whether that’s more chunking strategies, extra integration tests, or better docs.

## License
[MIT License](LICENSE)
