# coach_project/middleware.py
# (Create this file in the same directory as settings.py)

import sys # Import sys to print to stderr if needed

class CorsDebugMiddleware:
    """
    Simple middleware to print outgoing response headers for debugging CORS issues.
    Place this *after* corsheaders.middleware.CorsMiddleware in settings.MIDDLEWARE.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        print("--- CorsDebugMiddleware Initialized ---") # Confirm middleware is loaded

    def __call__(self, request):
        # Let the view process the request and get the response
        response = self.get_response(request)

        # --- Check headers on the outgoing response ---
        # Check specifically for API request paths
        # (Adjust '/api/' if your API paths have a different base)
        if request.path.startswith('/api/'):
            print("\n--- CORS DEBUG MIDDLEWARE (Outgoing Response) ---")
            print(f"Request Path: {request.path}")
            print(f"Request Origin Header: {request.headers.get('Origin')}") # What origin did the request come from?
            print(f"Response Status Code: {response.status_code}")
            print("Response Headers:")
            # Print all response headers, especially CORS ones
            # Using response.items() is safer than response.headers.items() for WSGIResponses
            for header, value in response.items():
                 print(f"  {header}: {value}")
            print("---------------------------------------------\n")
            # Optional: Print to stderr as well, sometimes logs differently
            # print("--- CORS DEBUG MIDDLEWARE (stderr) ---", file=sys.stderr)
            # for header, value in response.items():
            #     print(f"  {header}: {value}", file=sys.stderr)
            # print("-------------------------------------\n", file=sys.stderr)


        return response
