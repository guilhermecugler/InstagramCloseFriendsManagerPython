# Author: Guilherme Cugler
# GitHub: guilhermecugler
# Email: guilhermecugler@gmail.com
# Contact: +5513997230761 (WhatsApp)

import json
import requests
import time
import asyncio
import httpx
import logging

def load_processed_ids(user):
    try:
        with open(f"processed_{user}.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"added": [], "removed": []}

def save_processed_ids(user, processed_ids):
    with open(f"processed_{user}.json", "w") as f:
        json.dump(processed_ids, f, indent=4)

def load_extracted_ids():
    try:
        with open("extracted_ids.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_extracted_ids(ids):
    with open("extracted_ids.json", "w") as f:
        json.dump(ids, f, indent=4)

def chunked(iterable, n):
    """Divide a lista em pedaços de tamanho n."""
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

def process_ids(app, mode, resume, ids=None):
    app.update_status("Processing IDs...")
    app.update_progress(0)
    app.log(f"============================================================")

    app.log(f"Starting processing in '{'addition' if mode == 'add' else 'removal'}' mode")
    logging.info("Starting processing in '%s' mode", 'addition' if mode == 'add' else 'removal')

    try:
        headers = get_headers(app)
        if ids is None:
            all_ids = asyncio.run(get_all_ids(headers, app))
        else:
            all_ids = ids

        all_ids = list(set(all_ids))
        if resume:
            processed = set(app.processed_ids["added"] + app.processed_ids["removed"])
            ids_to_process = [id for id in all_ids if id not in processed]
            app.log(f"Resuming from where left off - {len(ids_to_process)} IDs remaining")
        else:
            ids_to_process = all_ids
            app.log(f"Starting from the beginning - {len(ids_to_process)} IDs to process")
            logging.info("Starting from the beginning - %d IDs to process", len(ids_to_process))

        total_ids = len(ids_to_process)
        for i, chunk in enumerate(chunked(ids_to_process, 500)):
            if not app.running:
                app.log("Processing interrupted by user")
                break

            app.update_status(f"Processing batch {i+1} ({len(chunk)} IDs)")
            app.update_progress(i / (total_ids / 500))

            try:
                added_set = set(app.processed_ids["added"])
                removed_set = set(app.processed_ids["removed"])
                current_chunk_set = set(chunk)

                if mode == "add":
                    removed_set -= current_chunk_set
                else:
                    added_set -= current_chunk_set

                if mode == "add":
                    added_set.update(current_chunk_set)
                else:
                    removed_set.update(current_chunk_set)

                app.processed_ids["added"] = list(added_set)
                app.processed_ids["removed"] = list(removed_set)

                save_processed_ids(app.current_user, app.processed_ids)

                response = requests.post(
                    'https://i.instagram.com/api/v1/stories/private_stories/bulk_update_members/',
                    headers=get_headers(app),
                    data={
                        'module': 'audience_selection',
                        'added_user_ids' if mode == 'add' else 'removed_user_ids': json.dumps(chunk)
                    },
                    verify=False
                )
                print(f'Status code: {response.status_code}')
                if response.status_code == 200:
                    app.log(f"Batch {i+1} processed successfully")
                    logging.info("Batch %d processed successfully", i+1)
                else:
                    app.log(f"Error in batch {i+1}: {response.text}")
                    app.processed_ids = load_processed_ids(app.current_user)

                time.sleep(1)

            except Exception as e:
                app.log(f"Critical error: {str(e)}")
                app.processed_ids = load_processed_ids(app.current_user)
                app.running = False
                break

        app.update_status("Processing completed")
        app.log(f"{'Added' if mode == 'add' else 'Removed'} {total_ids} close friends!", color="green")
        app.update_progress(1)

    except Exception as e:
        app.log(f"Error during processing: {str(e)}", color="red")
        logging.error("Error during processing: %s", str(e))
        app.update_status("Error during processing")

    finally:
        app.running = False

async def get_all_ids(headers, app):
    followers = await get_followers(headers, app)
    following = await get_following(headers, app)
    all_ids = list(set(followers + following))
    app.log(f"Total unique IDs found: {len(all_ids)}")
    return all_ids

async def get_followers(headers, app, max_id=''):
    params = {
        'search_surface': 'reel_viewer_settings_page',
    }
    url = f"https://i.instagram.com/api/v1/friendships/followers/"
    if max_id:
        params['max_id'] = max_id
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
        data = response.json()
        followers = [user['pk'] for user in data.get('users', [])]
        next_max_id = data.get('next_max_id')
        if next_max_id:
            followers += await get_followers(headers, app, max_id=next_max_id)
            app.update_status(f"Extracted {len(followers)} followers")

    return followers

async def get_following(headers, app, max_id=''):
    params = {
        'search_surface': 'reel_viewer_settings_page',
    }
    url = f"https://i.instagram.com/api/v1/friendships/following/"
    if max_id:
        params['max_id'] = max_id
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
        data = response.json()
        following = [user['pk'] for user in data.get('users', [])]
        next_max_id = data.get('next_max_id')
        if next_max_id:
            following += await get_following(headers, app, max_id=next_max_id)
            app.update_status(f"Extracted {len(following)} following")

    return following

def bulk_update(app, ids, operation):
    app.update_progress(0)
    chunk_size = 500
    total = len(ids)
    total_chunks = (total + chunk_size - 1) // chunk_size  # Calculate total number of chunks
    key = "added" if operation == "add" else "removed"
    opposite_key = "removed" if operation == "add" else "added"

    for i in range(0, total, chunk_size):
        if not app.running:
            app.log("Processing interrupted by user")
            break

        chunk = ids[i:i+chunk_size]
        app.log(f"Processing batch {i//chunk_size + 1} ({len(chunk)} users)")

        try:
            added_set = set(app.processed_ids["added"])
            removed_set = set(app.processed_ids["removed"])
            current_chunk_set = set(chunk)

            if operation == "add":
                removed_set -= current_chunk_set
            else:
                added_set -= current_chunk_set

            if operation == "add":
                added_set.update(current_chunk_set)
            else:
                removed_set.update(current_chunk_set)

            app.processed_ids["added"] = list(added_set)
            app.processed_ids["removed"] = list(removed_set)

            save_processed_ids(app.current_user, app.processed_ids)

            response = requests.post(
                'https://i.instagram.com/api/v1/stories/private_stories/bulk_update_members/',
                headers=get_headers(app),
                data={
                    'module': 'audience_selection',
                    'added_user_ids' if operation == "add" else 'removed_user_ids': json.dumps(chunk)
                },
                verify=False
            )
            print(f'Status code: {response.status_code}')
            if response.status_code == 200:
                app.log(f"Batch {i//chunk_size + 1} processed successfully")
            else:
                app.log(f"Error in batch {i//chunk_size + 1}: {response.text}")
                app.processed_ids = load_processed_ids(app.current_user)

            app.update_progress(total_chunks / total * (i//chunk_size + 1))
            time.sleep(1)

        except Exception as e:
            app.log(f"Critical error: {str(e)}")
            app.processed_ids = load_processed_ids(app.current_user)
            app.running = False
            break

def extract_ids(app):
    app.update_status("Extracting IDs...")
    app.log("Starting ID extraction...(This may take a while if you have a lot of followers or following...)")
    logging.info("Starting ID extraction")

    try:
        headers = get_headers(app)
        all_ids = asyncio.run(get_all_ids(headers, app))
        save_extracted_ids(all_ids)
        app.log(f"Extracted {len(all_ids)} followers and following successfully!", color="green")
        logging.info("Extracted %d followers and following successfully", len(all_ids))
        app.update_status("ID extraction completed")
        app.update_progress(1)
        return all_ids

    except Exception as e:
        app.log(f"Error during ID extraction: {str(e)}", color="red")
        logging.error("Error during ID extraction: %s", str(e))
        app.update_status("Error during ID extraction")

    finally:
        app.running = False

def get_headers(app):
    return {
        'accept': '*/*',
        'cookie': f'ds_user_id={app.loaded_session["user_id"]}; '
                 f'csrftoken={app.loaded_session["cookies"]["csrftoken"]}; '
                 f'sessionid={app.loaded_session["cookies"]["sessionid"]}',
        'x-csrftoken': app.loaded_session["cookies"]["csrftoken"],
        'x-ig-app-id': '936619743392459',
    }
