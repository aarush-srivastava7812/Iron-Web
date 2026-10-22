import test from "node:test";
import assert from "node:assert/strict";
import {agentWork, publicSource, stopCost} from "./agent-findings.js";

test("new findings show recommendations without execution or model internals",()=>{
  const html=agentWork([{agent_id:"stay_agent",status:"ok",summary:"SECRET_SUMMARY",
    execution:{mode:"tinyfish",persona:"SECRET_PERSONA",goal:"SECRET_GOAL",decision:"SECRET_DECISION",observations:["SECRET_OBSERVATION"],tool_calls:["SECRET_TOOL"]},
    presentation:{status:"ready",overview:"A stay to compare",findings:[{title:"Garden House",detail:"Near the old town",price:"₹2,500 per room / night",source_url:"https://example.com/hotel"}],notes:[],sources:["https://example.com/hotel"]}}]);
  assert.match(html,/Garden House/);assert.match(html,/Near the old town/);assert.match(html,/₹2,500/);
  assert.match(html,/TinyFish web research/);assert.doesNotMatch(html,/SECRET|Observed work|tool_calls/);
});

test("historical plans do not display raw traces or present unknown rates as zero",()=>{
  const html=agentWork([{agent_id:"stay_agent",status:"ok",summary:"SECRET_SUMMARY",execution:{decision:"SECRET_DECISION"},stay_options:[{name:"Unpriced stay",price_per_night_inr:null,pros:["Courtyard"]}]}]);
  assert.match(html,/Unpriced stay/);assert.match(html,/Nightly rate to confirm/);
  assert.doesNotMatch(html,/SECRET|₹0|completed/);
  assert.match(agentWork([{agent_id:"food_guide_agent",status:"ok",evidence:[]}]),/Needs confirmation/);
});

test("escape travel content, reject unsafe links and omit reasoning payloads",()=>{
  for(const url of ["javascript:alert(1)","https://user:secret@example.com","https://127.0.0.1/private","https://localhost/private"] )assert.equal(publicSource(url),null);
  const html=agentWork([{agent_id:"stay_agent",presentation:{status:"ready",overview:"<think>private</think>",findings:[{title:'<img src=x onerror=alert(1)>',detail:"A courtyard",source_url:"javascript:alert(1)"}],notes:[],sources:[]}}]);
  assert.doesNotMatch(html,/<img|<think|private|href="javascript:/);assert.match(html,/&lt;img/);
});

test("failed historical results cannot show stale candidates as recommendations",()=>{
  const html=agentWork([{agent_id:"stay_agent",status:"failed",summary:"API_KEY private",stay_options:[{name:"Stale recommendation"}]}]);
  assert.match(html,/Could not complete/);assert.doesNotMatch(html,/Stale recommendation|API_KEY|private/);
  assert.equal(agentWork([]),"");
});

test("unquoted visits are not free and rest windows have no invented price",()=>{
  const stop={kind:"food",title:"Lunch at Garden Cafe",est_cost_inr:0,evidence:{source:"tinyfish.web"}};
  assert.equal(stopCost(stop,[{name:"Garden Cafe",approx_price_per_guest_inr:null}]),"Price to confirm");
  assert.equal(stopCost(stop),"Price to confirm");
  assert.equal(stopCost({...stop,kind:"buffer"}),"Time reserved");
  assert.equal(stopCost({kind:"attraction",title:"Public garden",est_cost_inr:0},[{name:"Public garden",price_per_person_inr:0}]),"₹0 / guest");
});
