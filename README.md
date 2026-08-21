Dev branch is developmental, consider it beta
#  <img src="https://github.com/Vansmak/OCDarr/assets/16037573/f802fece-e884-4282-8eb5-8c07aac1fd16" alt="logo" width="200"/>

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/vansmak)

## OCDarr: Precision Episode Management for Sonarr 

OCDarr is a smart media assistant that gives you episode-by-episode control over your library, automatically preparing what you want to watch next while cleaning up what you've already seen.

## Navigation Features 

📺 **Shows**  
Browse your series collection with intuitive displays of recently added and upcoming episodes.

🎬 **Movies**  
Manage your movie library with easy access to recently added titles and missing content.

⬇️ **Requests**  
Streamlined interface for adding new content requests with season and episode-level precision.

▶️ **Plex Watchlist**  
watchlist, favorites and stats, see what's missing from your collection.

⚙️ **Settings**  
Choose default download profiles and rule configuration.


🔬 **Rule-Based Episode Control**
The heart of OCDarr - create custom rules to determine exactly how many episodes to monitor, search for, and retain.

## Perfect For Users Who:
- Don't rewatch or keep, yet its ok if you do
- Want the next episode ready when they finish the current one
- Prefer to keep their media library tidy and organized, not as vauluable for hoarders
- Don't need to keep entire seasons after watching, but you can
- Want different management rules for different shows
- Use Overseerr or Jellyseerr but want to  manage at the episode level, nzb360, lunasea (use tag)

Most media management tools operate on an all-or-nothing approach. OCDarr revolutionizes this with its dynamic, per-show rule system:

> Granular Episode Selection: Choose exactly which episodes you want  
> Intelligent Cleanup: Automatically manage your library based on your viewing habits  
> Flexible Rules: Create custom management strategies for different shows  

## How It Works

### Rule Components: Your Media, Your Rules

**Get Option**: Control how many upcoming episodes to prepare
- 1: Just the next episode
- 3: Next three episodes
- season: Full season
- all: Everything upcoming                                                  

**Action Option**: Define how episodes are handled
- monitor: Passive tracking
- search: Active download and monitoring

**Keep Watched**: Manage post-viewing library
- 1: Keep only the last watched episode
- 2: Keep last two episodes
- season: Retain current season
- all: Keep everything

**Monitor Watched**: Tracking behavior after watching
- true: Keep watched episodes monitored
- false: Automatically unmonitor after viewing
                                    
### 🎬 Adaptive Episode Request Workflows

OCDarr supports multiple request scenarios with intelligent handling:

**External Requests (Jellyseerr/Overseerr)**

*Use "episodes" tag when requesting something from Jellyseerr/Overseerr if you want to control down to individual episodes*

With "episodes" tag:
- Precise episode selection
- Unmonitor all initial episodes
- Cancel automatic downloads
- User-guided episode monitoring

Without "episodes" tag:
- Instant addition to default rule
- Automatic management based on predefined preferences

**Internal Requests (OCDarr Interface)**
- Identical powerful selection mechanism
- Pilot episode handling
- Granular episode monitoring

### 🌟 Real-World Scenario

Example: You're watching "Breaking Bad"
  
You want:
- Only the next episode ready
- Automatically clean up watched episodes
- Keep the current season
- Stop tracking after you've finished

Traditional Solution: Download entire seasons, manual cleanup  
OCDarr Solution: Intelligent, automated, personalized management

### 🔑 Key Differentiators

🎯 Episode-level control  
🧹 Automatic library management  
🔧 Highly configurable rules  
🚀 Proactive episode preparation  
📰 RSS News Tickers

OCDarr isn't just a tool—it's your personal media librarian.
## 📰 RSS News Tickers

OCDarr includes customizable RSS tickers in each main section that display relevant media news and updates:

- **Shows Tab**: Displays TV industry news via TVLine's feed
- **Movies Tab**: Shows movie trailer updates from FilmJabber
- **Plex Tab**: Displays upcoming media releases from ComingSoon.net

### Features:
- Auto-scrolling text tickers present the latest entertainment headlines
- Each section has its own topic-focused feed
- Configurable via settings icon (desktop only)
- Hidden on mobile devices to maximize screen space
- Preset feed options or custom RSS URL support

Tickers automatically refresh every 30 minutes to ensure you always see the latest entertainment news without leaving OCDarr.

> 💡 **Tip**: The Plex section ticker would be a great place to add a friends' watchlist feed if you're using a service that provides RSS feeds of user activity.

### Interface Preview!
[ocdarr](https://github.com/user-attachments/assets/5b97f9f3-bd2a-4df7-8fc5-1e9873e7d4fa)


![ocd](https://github.com/user-attachments/assets/cd7b5c0f-275f-4222-99e6-40fd76c6f495)

## 📋 Requirements

- Sonarr v3
- Plex + Tautulli
- Docker environment
- Overseerr/Jellyseerr (optional, for automatic rule assignment)

## 🚀 Installation

### Option 1: Docker Hub (Recommended)

# Pull the image
```
docker pull vansmak/ocdarr:amd64_dev
```
# Run the container
```bash
docker run -d \
  --name ocdarr \
  --env-file .env \
  --env CONFIG_PATH=/app/config/config.json \
  -p 5002:5002 \
  -v ${PWD}/logs:/app/logs \
  -v ${PWD}/config:/app/config \
  -v ${PWD}/temp:/app/temp \
  --restart unless-stopped \
  vansmak/ocdarr:amd64_dev
```

## Option 2: Build from Source (Development)
```bash
git clone https://github.com/Vansmak/OCDarr.git
cd OCDarr
git checkout dev
docker-compose up -d --build
```

## ⚙️ Configuration

### Environment Variables
Create a .env file:
```env
SONARR_URL=url:port
SONARR_API_KEY=YOUR_SONARR_API_KEY_HERE 
JELLYSEERR_URL=url:port #LEAVE LABEL AS JELLYSEER BUT USE YOUR OVERSEER URL AND API
JELLYSEERR_API_KEY=api_key
RADARR_URL=url:port
RADARR_API_KEY=api_key
TMDB_API_KEY=reallylongtmdbkey
PLEX_URL=plex_url:port
PLEX_TOKEN=plex_token
MAX_TMDB_ITEMS=24
MAX_SHOWS_ITEMS=24
MAX_MOVIES_ITEMS=24
```

### Docker Compose (Production)
```yaml
version: '3.8'
services:
  ocdarr:
    image: vansmak/ocdarr:amd64_dev
    environment:
      - SONARR_URL=${SONARR_URL}
      - SONARR_API_KEY=${SONARR_API_KEY}
      - JELLYSEERR_URL=${JELLYSEERR_URL}
      - JELLYSEERR_API_KEY=${JELLYSEERR_API_KEY}
      - RADARR_URL=${RADARR_URL}
      - RADARR_API_KEY=${RADARR_API_KEY}
      - TMDB_API_KEY=${TMDB_API_KEY}
      - CONFIG_PATH=/app/config/config.json
      - PLEX_URL=${PLEX_URL}
      - PLEX_TOKEN=${PLEX_TOKEN}
      - MAX_TMDB_ITEMS=24
      - MAX_SHOWS_ITEMS=24
      - MAX_MOVIES_ITEMS=24
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
      - ./temp:/app/temp
      # DO NOT mount templates or static - they're included in the Docker image
    ports:
      - "5002:5002"
    restart: unless-stopped
```

### Docker Compose (Development)
```yaml
version: '3.8'
services:
  ocdarr:
    build:
      context: .
      dockerfile: Dockerfile
    env_file:
      - .env
    volumes:
      - .:/app  # Mount entire directory for development
      - ./logs:/app/logs
      - ./config:/app/config
      - ./temp:/app/temp
    ports:
      - "5002:5002"
    restart: unless-stopped
```
# OcDarr for Unraid

Flask application that provides integrated webhook functionality for Sonarr, Radarr, Jellyseerr, and Plex.

## For Unraid Users

To install this Docker container on Unraid:

1. Navigate to the "Docker" tab in your Unraid web UI
2. Click on the "Docker Repositories" sub-tab
3. Add `https://github.com/vansmak/OCDarr` to your template repositories
4. Click "Save"
5. Go back to the "Docker" tab
6. Click "Add Container"
7. Find "OcDarr" in the template dropdown
8. Configure the container settings as needed
9. Click "Apply"

## Architecture Support

This container is designed for AMD64/x86_64 systems only. It will not work on ARM-based Unraid servers.

## Configuration

The following environment variables are required:

### Media Servers
- `SONARR_URL`: URL for your Sonarr instance
- `SONARR_API_KEY`: API key for your Sonarr instance
- `RADARR_URL`: URL for your Radarr instance
- `RADARR_API_KEY`: API key for your Radarr instance
- `JELLYSEERR_URL`: URL for your Jellyseerr instance
- `JELLYSEERR_API_KEY`: API key for your Jellyseerr instance
- `PLEX_URL`: URL for your Plex server
- `PLEX_TOKEN`: Authentication token for your Plex server

### External APIs
- `TMDB_API_KEY`: API key for The Movie Database

### Optional Settings
- `MAX_TMDB_ITEMS`: Maximum number of TMDB items to display (default: 24)
- `MAX_SHOWS_ITEMS`: Maximum number of shows to display (default: 24)
- `MAX_MOVIES_ITEMS`: Maximum number of movies to display (default: 24)
- `LOG_PATH`: Path to application log file (default: /app/logs/app.log)
- `MISSING_LOG_PATH`: Path to missing items log file (default: /app/logs/missing.log)
- `FLASK_DEBUG`: Enable Flask debug mode (default: false)

Docker image: [vansmak/ocdarr:amd64_dev](https://hub.docker.com/r/vansmak/ocdarr)
📝 Rules System
Create rules using the OCDarr website (start with Default rule)

Rules define how OCDarr manages each show. Each rule has four components:

Get Option (get_option): 

  1 - Get only the next episode
  3 - Get next three episodes
  season - Get full seasons
  all - Get everything upcoming  

Action Option (action_option):

  monitor - Only monitor episodes
  search - Monitor and actively search

Keep Watched (keep_watched):

  1 - Keep only last watched episode
  2 - Keep the last 2, etc
  season - Keep current season
  all - Keep everything

Monitor Watched (monitor_watched):

  true - Keep watched episodes monitored
  false - Unmonitor after watching

Rule Assignment
Shows can get rules in two ways:
Default Rule: Applied if no other rule matches
This is the first rule you should edit to how you want most shows added as it will be applied if no other rule is set.
For example, a typical Default rule might be:
```
"rules": {
    "Default": {
        "get_option": "1",
        "action_option": "search",
        "keep_watched": "1",
        "monitor_watched": true
    }
}
```
Manual Assignment: Through OCDarr's web interface
Automatic via Tags: When requesting shows through Overseerr/Jellyseerr

Without tag: Goes to default rule
With "episodes" tag: Applies no rule and presents form to select episodes

🔗 Media Server Integration
Plex (via Tautulli) Setup

In Tautulli, go to Settings > Notification Agents
Click "Add a new notification agent" and select "Webhook"
Configure the webhook:

Webhook URL: http://your-ocdarr-ip:5002/webhook/<your-webhook-secret>
(the secret is auto-generated on first run and stored in config.json as "webhook_secret" — check there for the current value)
Trigger: Episode Watched
JSON Data: Use exactly this template:
```
{
  "plex_title": "{show_name}",
  "plex_season_num": "{season_num}",
  "plex_ep_num": "{episode_num}"
}
```
![webhook](https://github.com/Vansmak/OCDarr/assets/16037573/cf0db503-d730-4a9c-b83e-2d21a3430ece)![webhook2](https://github.com/Vansmak/OCDarr/assets/16037573/45be66c2-1869-49c1-8074-9081ed7c913b)
![webhook3](https://github.com/Vansmak/OCDarr/assets/16037573/24f02a75-2100-4b2a-9137-ce1e68803d1f)![webhook4](https://github.com/Vansmak/OCDarr/assets/16037573/f82198fc-e4c4-40ec-a9c7-551b2d8cdccd)

Important: Adjust your "Watched Percentage" in Tautulli's general settings to control when webhooks trigger.

### Jellyseerr/Overseerr Webhook Setup

*This is used with the episodes tag to cancel the request after it's added to Sonarr. If you want requests to stay in Jellyseerr/Overseerr, don't use the episodes tag when requesting.*

1. In Jellyseerr, go to Settings > Notifications
2. Add a new webhook notification
3. Set the webhook URL to `http://yourocdarr:5002/seerr-webhook`
4. Enable notifications for "Request Approved"
5. Save the webhook configuration

### Sonarr Webhook Setup

1. In Sonarr, go to Settings > Connect
2. Click the + button to add a new connection
3. Select "Webhook"
4. Configure:
   - URL: `http://your-ocdarr-ip:5002/sonarr-webhook`
   - Triggers: Enable "On Series Add"
   - Leave other settings at default

### Sonarr Delayed Release Profile

*This buys time while the script unmonitors episodes so downloads don't start*

1. Settings > Profiles > Add delay profile
2. Add a ridiculous time like 10519200 (this is just to prevent downloads, it won't download anything less than 20 years old, it's a failsafe)
3. Choose episodes tag
4. Do not select bypass

## 📋 Episode Selection Flow

OCDarr supports multiple ways to request and manage TV shows:

### External Requests (via Jellyseerr/Overseerr)

When requesting shows through Jellyseerr:

**With "episodes" tag**: Follows the episode selection flow:
1. Show is sent to Sonarr
2. All episodes are unmonitored
3. Downloads are canceled
4. A pending season selection request is created
5. User selects episodes
6. If only S01E01 is selected: Episodes tag is removed, show is added to default rule
7. If multiple episodes: Episodes tag is kept, only selected episodes are monitored
8. Original Jellyseerr request is canceled automatically

**Without "episodes" tag**: Show is directly added to the default rule

### Internal Requests (via OCDarr)

When requesting shows through OCDarr's interface:
1. Show is added to Sonarr with episodes tag
2. All episodes are unmonitored
3. Downloads are canceled
4. A pending season selection request is created
5. User selects episodes
6. If only E01 is selected: Episodes tag is removed, show is added to default rule (meant to mimic pilot episode)
7. If multiple episodes: Episodes tag is kept, only selected episodes are monitored

This system gives you precise control over exactly which episodes you want, while cleaning up appropriately after requests.

## 🔧 Troubleshooting

### Common Issues

**Shows aren't updating after watching episodes:**
- Verify Tautulli webhook is properly configured
- Check OCDarr logs for incoming webhook data
- Ensure the show has a rule assigned

**Rule not applying correctly:**
- Edit config.json directly if UI changes aren't saving
- Verify the show isn't using the "episodes" tag which overrides rules
- Check Sonarr for any manual changes that might conflict

**Docker container won't start:**
- Verify environment variables are set correctly
- Check folder permissions for mounted volumes
- Review logs for specific error messages

For additional support, please open an issue on GitHub.

## 📊 Version History

**v0.9.0-beta (Current Dev Branch)**
- Added Plex Watchlist integration
- Improved request handling
- UI refinements

**v0.8.0-alpha**
- Initial public release
- Core rule functionality
- Basic integration with Sonarr and Jellyseerr/Overseerr

*Not designed for media hoarders or large household servers with multiple users at different points in series.
Use is intended for owned media or paid subscription services.*
