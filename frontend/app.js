const API_BASE = "http://127.0.0.1:8000";

const chatForm = document.getElementById("chatForm");
const queryInput = document.getElementById("queryInput");
const cityInput = document.getElementById("cityInput");

const messages = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const chatContainer = document.getElementById("chatContainer");

const sendButton = document.getElementById("sendButton");

const weatherPanel = document.getElementById("weatherPanel");

const connectionText =
    document.getElementById("connectionText");

const connectionDot =
    document.querySelector(".connection-dot");

let conversationStarted = false;


/* =========================================================
   ESCAPE HTML
========================================================= */

function escapeHtml(text = "") {

    return text.replace(
        /[&<>"']/g,
        character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        })[character]
    );
}


/* =========================================================
   SIMPLE MARKDOWN RENDERER
========================================================= */

function renderMarkdown(text = "") {

    let html = escapeHtml(text);

    /*
     * Headings
     */

    html = html.replace(
        /^### (.+)$/gm,
        "<h3>$1</h3>"
    );

    html = html.replace(
        /^## (.+)$/gm,
        "<h2>$1</h2>"
    );

    html = html.replace(
        /^# (.+)$/gm,
        "<h1>$1</h1>"
    );


    /*
     * Bold
     */

    html = html.replace(
        /\*\*(.+?)\*\*/g,
        "<strong>$1</strong>"
    );


    /*
     * Italic
     */

    html = html.replace(
        /\*(.+?)\*/g,
        "<em>$1</em>"
    );


    /*
     * Bullet points
     */

    html = html.replace(
        /^\* (.+)$/gm,
        "<li>$1</li>"
    );

    html = html.replace(
        /(<li>.*<\/li>\s*)+/g,
        match => `<ul>${match}</ul>`
    );


    /*
     * Paragraphs
     */

    html = html.replace(
        /\n\n+/g,
        "</p><p>"
    );

    html = html.replace(
        /\n/g,
        "<br>"
    );


    return `<p>${html}</p>`;
}


/* =========================================================
   ADD USER MESSAGE
========================================================= */

function addUserMessage(text) {

    const message = document.createElement("div");

    message.className =
        "message user";

    message.innerHTML = `
        <div class="message-bubble">
            ${escapeHtml(text)}
        </div>
    `;

    messages.appendChild(message);

    scrollMessages();
}


/* =========================================================
   ADD ASSISTANT MESSAGE
========================================================= */

function addAssistantMessage(text) {

    const message = document.createElement("div");

    message.className =
        "message assistant";

    message.innerHTML = `

        <div class="message-avatar">
            ☁
        </div>

        <div class="message-bubble">
            ${renderMarkdown(text)}
        </div>

    `;

    messages.appendChild(message);

    scrollMessages();
}


/* =========================================================
   TYPING MESSAGE
========================================================= */

function addTypingMessage() {

    const message = document.createElement("div");

    message.className =
        "message assistant";

    message.id =
        "typingMessage";

    message.innerHTML = `

        <div class="message-avatar">
            ☁
        </div>

        <div class="message-bubble">

            <div class="typing">
                <span></span>
                <span></span>
                <span></span>
            </div>

        </div>

    `;

    messages.appendChild(message);

    scrollMessages();

    return message;
}


/* =========================================================
   SCROLL
========================================================= */

function scrollMessages() {

    messages.scrollTo({
        top: messages.scrollHeight,
        behavior: "smooth"
    });
}


/* =========================================================
   START CHAT UI
========================================================= */

function startConversation() {

    if (conversationStarted) {
        return;
    }

    conversationStarted = true;

    welcome.style.display =
        "none";

    chatContainer.classList.add(
        "active"
    );
}


/* =========================================================
   WEATHER CODE
========================================================= */

function weatherIcon(code) {

    const value =
        Number(code);

    if (value === 0) {
        return "☀️";
    }

    if ([1, 2].includes(value)) {
        return "⛅";
    }

    if (value === 3) {
        return "☁️";
    }

    if ([45, 48].includes(value)) {
        return "🌫️";
    }

    if ([51, 53, 55].includes(value)) {
        return "🌦️";
    }

    if (
        [
            61,
            63,
            65,
            80,
            81,
            82
        ].includes(value)
    ) {
        return "🌧️";
    }

    if (
        [
            95,
            96,
            99
        ].includes(value)
    ) {
        return "⛈️";
    }

    return "🌤️";
}


/* =========================================================
   WEATHER DESCRIPTION
========================================================= */

function weatherDescription(code) {

    const value =
        Number(code);

    if (value === 0) {
        return "Clear sky";
    }

    if ([1, 2].includes(value)) {
        return "Partly cloudy";
    }

    if (value === 3) {
        return "Overcast";
    }

    if ([45, 48].includes(value)) {
        return "Foggy";
    }

    if ([51, 53, 55].includes(value)) {
        return "Drizzle";
    }

    if (
        [
            61,
            63,
            65,
            80,
            81,
            82
        ].includes(value)
    ) {
        return "Rain";
    }

    if (
        [
            95,
            96,
            99
        ].includes(value)
    ) {
        return "Thunderstorm";
    }

    return "Mixed conditions";
}


/* =========================================================
   UPDATE WEATHER CARD
========================================================= */

function updateWeather(data) {

    if (!data || !data.weather) {
        return;
    }

    const weather =
        data.weather;

    const current =
        weather.current;

    const daily =
        weather.daily || [];


    /*
     * Location
     */

    const location =
        data.location || {};

    document.getElementById(
        "weatherLocation"
    ).textContent =
        location.city ||
        cityInput.value ||
        "Weather";


    /*
     * Current
     */

    if (current) {

        document.getElementById(
            "temperature"
        ).textContent =
            current.temperature ?? "--";


        document.getElementById(
            "weatherCondition"
        ).textContent =
            weatherDescription(
                current.weather_code
            );


        document.getElementById(
            "feelsLike"
        ).textContent =
            current.feels_like != null
                ? `${current.feels_like}°`
                : "--";


        document.getElementById(
            "humidity"
        ).textContent =
            current.humidity != null
                ? `${current.humidity}%`
                : "--";


        document.getElementById(
            "wind"
        ).textContent =
            current.wind_speed != null
                ? `${current.wind_speed} km/h`
                : "--";


        document.getElementById(
            "rain"
        ).textContent =
            current.precipitation != null
                ? `${current.precipitation} mm`
                : "--";
    }


    /*
     * Forecast
     */

    const forecast =
        document.getElementById(
            "forecast"
        );

    forecast.innerHTML = "";


    daily
        .slice(0, 5)
        .forEach(day => {

            const date =
                new Date(day.date);

            const dayName =
                date.toLocaleDateString(
                    undefined,
                    {
                        weekday: "short"
                    }
                );


            const card =
                document.createElement("div");

            card.className =
                "forecast-day";


            card.innerHTML = `

                <div class="forecast-day-name">
                    ${dayName}
                </div>

                <div class="forecast-icon">
                    ${weatherIcon(day.weather_code)}
                </div>

                <div class="forecast-temp">
                    ${day.temperature_max ?? "--"}°
                    /
                    ${day.temperature_min ?? "--"}°
                </div>

                <div class="forecast-rain">
                    💧 ${day.precipitation ?? 0} mm
                </div>

            `;


            forecast.appendChild(card);

        });


    weatherPanel.classList.remove(
        "hidden"
    );
}


/* =========================================================
   SEND MESSAGE
========================================================= */

async function sendMessage(query) {

    const city =
        cityInput.value.trim() ||
        "Chennai";


    startConversation();

    addUserMessage(query);


    const typing =
        addTypingMessage();


    sendButton.disabled = true;

    queryInput.disabled = true;


    try {

        const response =
            await fetch(
                `${API_BASE}/chat`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        query: query,

                        location: {
                            city: city
                        },

                        language: "English",

                        channel: "web"

                    })
                }
            );


        const data =
            await response.json();


        typing.remove();


        if (!response.ok) {

            addAssistantMessage(
                data.detail ||
                "Something went wrong while contacting WeatherGPT."
            );

            return;
        }


        /*
         * Render AI response
         */

        addAssistantMessage(
            data.bot_reply ||
            "I couldn't generate a response."
        );


        /*
         * Render weather data
         */

        updateWeather(data);


    } catch (error) {

        console.error(error);


        typing.remove();


        addAssistantMessage(
            "I couldn't connect to the WeatherGPT backend. " +
            "Please make sure your FastAPI server is running on port 8000."
        );

    } finally {

        sendButton.disabled = false;

        queryInput.disabled = false;

        queryInput.focus();

    }
}


/* =========================================================
   FORM SUBMIT
========================================================= */

chatForm.addEventListener(
    "submit",
    event => {

        event.preventDefault();

        const query =
            queryInput.value.trim();


        if (!query) {
            return;
        }


        queryInput.value = "";

        queryInput.style.height =
            "auto";


        sendMessage(query);

    }
);


/* =========================================================
   ENTER TO SEND
========================================================= */

queryInput.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            chatForm.requestSubmit();

        }

    }
);


/* =========================================================
   AUTO RESIZE TEXTAREA
========================================================= */

queryInput.addEventListener(
    "input",
    () => {

        queryInput.style.height =
            "auto";

        queryInput.style.height =
            `${Math.min(
                queryInput.scrollHeight,
                130
            )}px`;

    }
);


/* =========================================================
   SUGGESTIONS
========================================================= */

document
    .querySelectorAll(
        "[data-question]"
    )
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                const question =
                    button.dataset.question;


                queryInput.value =
                    question;


                queryInput.focus();

            }
        );

    });


/* =========================================================
   NEW CHAT
========================================================= */

document
    .getElementById("newChat")
    .addEventListener(
        "click",
        clearConversation
    );


document
    .getElementById("clearChat")
    .addEventListener(
        "click",
        clearConversation
    );


function clearConversation() {

    messages.innerHTML = "";

    conversationStarted =
        false;

    chatContainer.classList.remove(
        "active"
    );

    welcome.style.display =
        "flex";

    weatherPanel.classList.add(
        "hidden"
    );

    queryInput.value = "";

    queryInput.focus();

}


/* =========================================================
   API HEALTH
========================================================= */

async function checkHealth() {

    try {

        const response =
            await fetch(
                `${API_BASE}/health`
            );


        if (!response.ok) {
            throw new Error(
                "API unavailable"
            );
        }


        connectionText.textContent =
            "API connected";

        connectionDot.classList.remove(
            "offline"
        );

    } catch {

        connectionText.textContent =
            "API offline";

        connectionDot.classList.add(
            "offline"
        );

    }

}


/* =========================================================
   INITIALIZATION
========================================================= */

checkHealth();