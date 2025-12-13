import { useEffect, useState } from "react";
import "../App.css";
const API_URL = "https://wc1j5prmsj.execute-api.us-east-1.amazonaws.com/dev/artifacts";

function Home() {
    const [models, setModels] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(API_URL, {
            method: "POST", // <-- this line changes the HTTP method
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ action: "list" }) // optional body if your backend expects one
        })
            .then((res) => res.json())
            .then((data) => {
                setModels(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Error fetching models:", err);
                setLoading(false);
            });
    }, []);

    return (
        <div className="content">
            <div className="card">
                <h2>Registered Models</h2>
                {loading ? (
                    <p>Loading models...</p>
                ) : models.length === 0 ? (
                    <p>No models found in the registry.</p>
                ) : (
                    <ul className="model-list">
                        {models.map((m) => (
                            <li key={m.id} className="model-item">
                                <strong>{m.name}</strong> — {m.status} <br />
                                <span className="model-meta">
                                    Submitted by {m.submittedBy} on{" "}
                                    {new Date(m.dateAdded).toLocaleString()}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}

export default Home;
