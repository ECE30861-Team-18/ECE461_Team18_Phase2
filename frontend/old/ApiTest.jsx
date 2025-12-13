import { useEffect } from "react";
import {
  getHealth,
  listArtifacts,
} from "../api/client";

export default function ApiTest() {
  useEffect(() => {
    async function runTests() {
      try {
        console.log("Health:", await getHealth());
        console.log("Artifacts:", await listArtifacts());
      } catch (err) {
        console.error("API test failed:", err);
      }
    }

    runTests();
  }, []);

  return <div>API tests running — check console</div>;
}
