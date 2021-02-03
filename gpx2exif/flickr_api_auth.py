import webbrowser

import flickrapi


def create_flickr_api(api_key, api_secret, perms="write", token_cache_location=None):
    flickr = flickrapi.FlickrAPI(
        api_key,
        api_secret,
        format="parsed-json",
        token_cache_location=token_cache_location,
    )
    if not flickr.token_valid(perms=perms):
        flickr.get_request_token(oauth_callback="oob")
        authorize_url = flickr.auth_url(perms=perms)
        webbrowser.open_new_tab(authorize_url)
        verifier = input("Verifier code: ")
        flickr.get_access_token(verifier)

    return flickr
