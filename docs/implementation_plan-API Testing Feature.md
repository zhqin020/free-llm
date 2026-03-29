# Provider API Testing Feature

The goal is to provide a way for users to verify if a provider's URL and API key are working correctly directly from the dashboard. This is especially useful because the `freellm-res` sync might provide website URLs instead of active API endpoints.

## Proposed Changes

### Backend (src/main.py)
#### [MODIFY] [main.py](file:///home/watson/work/freellm/src/main.py)
- Create a new `ProviderTestRequest` Pydantic model.
- Add a new `@app.post("/admin/providers/test")` endpoint.
- The endpoint will use the [AdapterRegistry](file:///home/watson/work/freellm/src/adapters.py#107-123) to pick the correct adapter based on the provider name/URL.
- It will execute a single chat completion request and return the result or error.

### Frontend (src/static/index.html)
#### [MODIFY] [index.html](file:///home/watson/work/freellm/src/static/index.html)
- Add an "API Test" button to each provider card.
- Create a new `test-modal` DIV in the HTML.
- Add JavaScript functions:
    - `openTestModal(providerName)`: Opens the modal and pre-fills the URL and first model ID.
    - `submitTest()`: Sends the test request to the backend.
    - `applyTestUrl()`: Updates the provider's URL in the main edit modal if the test was successful.

## Verification Plan
### Automated Tests
- Use `curl` to test the new `/admin/providers/test` endpoint with valid and invalid URLs.

### Manual Verification
1. Open the dashboard.
2. Click the "API Test" button for a provider with a known bad URL (e.g., Mistral's website).
3. Verify that the test fails and shows the error (e.g., "Failed to parse JSON").
4. Correct the URL in the test modal and submit again.
5. Verify that the test succeeds and shows the LLM's response.
6. Click "Update URL" and verify that the provider's record is updated in the database.
