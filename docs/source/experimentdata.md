# Experiment data (non-video)

### Accessing experiment data

You can see and download collected responses either via the Lookit experimenter interface 
or using the API.

A researcher with edit permissions for a particular study can download session data in JSON or CSV format via the Experimenter interface. A session record in a Postgres database is created each time a participant starts the study, and includes a timestamp, account information, condition assignment, the sequence of frames the participant actually saw, and frame-specific information for each frame (included in an ‘expData’ structure which is a JSON object with keys corresponding to frame nicknames as defined in the study definition JSON). Each frame type may save different data, e.g. form responses; frames that record webcam video include the video filename(s). The data captured by a particular frame are listed in the frame documentation at http://centerforopenscience.github.io/exp-addons, under ‘Methods’ > ‘serializeContent’. Additionally, event data is captured for each frame and included under an eventTimings key within the frame data JSON, minimally including a timestamped event when the user proceeds to the next frame. These events are listed under ‘Events’ in the documentation.

### Structure of session data

The data saved when a subject participates in a study varies based on how that experiment 
is defined. The general structure for this **session** data is:

```json
{
    "type": "object",
    "properties": {
        "profileId": {
            "type": "string",
            "pattern": "\w+\.\w+"
        },
        "experimentId": {
            "type": "string",
            "pattern": "\w+"
        },
        "experimentVersion": {
            "type": "string"
        },
        "completed": {
            "type": "boolean"
        },
        "sequence": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "conditions": {
            "type": "object"
        },
        "expData": {
            "type": "object"
        },
        "feedback": {
            "$oneOf": [{
                "type": "string"
            }, null]
        },
        "hasReadFeedback": {
            "$oneOf": [{
                "type": "boolean"
            }, null]
        },
        "globalEventTimings": {
            "type": "array",
            "items": {
                "type": "object"
            }
        }
    },
    "required": [
        "profileId",
        "experimentId",
        "experimentVersion",
        "completed",
        "sequence",
        "expData"
    ]
}
```

These properties are described below:

- *profileId*: This unique identifier of the participant. This field follows the form: `<account.id>.<profile.id>`, where `<account.id>` is the unique identifier of the associated account, and `<profile.id>` is the unique identifier of the profile active during this particular session (e.g. the participating child). Account data is stored in a separate database, and includes demographic survey data and the list of profiles associated with the account.
- *experimentId*: The unique identifier of the study the subject participated in. 
- *experimentVersion*: The unique identifier of the version of the study the subject participated in. TODO: more on JamDB, versioning
- *completed*: A true/false flag indicating whether or not the subject completed the study.
- *sequence*: The sequence of **frames** the subject actually saw (after running randomization, etc.)
- *conditions*: For randomizers, this records what condition the subject was assigned
- *expData*: A JSON object containing the data collected by each **frame** in the study. More on this to follow.
- *feedback*: Some researchers may have a need to leave some session-specific feedback for a subject; this is shown to the participant in their 'completed studies' view.
- *hasReadFeedback*: A true/false flag to indicate whether or not the given feedback has been read.
- *globalEventTimings*: A list of events recorded during the study, not tied to a particular frame. Currently used for recording early exit from the study; an example value is 

```json
"globalEventTimings": [
        {
            "exitType": "browserNavigationAttempt", 
            "eventType": "exitEarly", 
            "lastPageSeen": 0, 
            "timestamp": "2016-11-28T20:00:13.677Z"
        }
    ]
```

### Example `expData`

Here's an example of data collected during a session (note: not all fields are shown):

```json
{
	"sequence": [
		"0-intro-video",
		"1-survey",
		"2-exit-survey"
	],
	"conditions": {
        "1-survey": {
            "parameterSet": {
                "QUESTION1": "What is your favorite color?",
                "QUESTION2": "What is your favorite number?"
            },
            "conditionNum": 0
        }
	},
	"expData": {
		"0-intro-video": {
			"eventTimings": [{
				"eventType": "nextFrame",
				"timestamp": "2016-03-23T16:28:20.753Z"
			}]
		},
		"1-survey": {
			"formData": {
				"name": "Sam",
				"favPie": "pecan"
			},
			"eventTimings": [{
				"eventType": "nextFrame",
				"timestamp": "2016-03-23T16:28:26.925Z"
			}]
		},
		"2-exit-survey": {
			"formData": {
				"thoughts": "Great!",
				"wouldParticipateAgain": "Yes"
			},
			"eventTimings": [{
				"eventType": "nextFrame",
				"timestamp": "2016-03-23T16:28:32.339Z"
			}]
		}
	}
}
```

Things to note:
- 'sequence' has resolved to three items following the pattern `<order>-<frame.id>`, where `<order>` is the order in 
  the overall sequence where this **frame** appeared, and `<frame.id>` is the identifier of the frame as defined in 
  the 'frames' property of the experiment structure. Notice in particular that since 'survey-2' was randomly selected, 
  it appears here.
- 'conditions' has the key/value pair `"1-survey": 1`, where the format `<order>-<frame.id>` corresponds 
  with the `<order>` from the 'sequence' of the *original* experiment structure, and the `<frame.id>` again corresponds 
  with the identifier of the frame as defined in 
  the 'frames' property of the experiment structure. Data will be stored in conditions for the first frame created by a randomizer (top-level only for now, i.e. not from nested randomizers). The data stored by a particular randomizer can be found under `methods: conditions` in the [randomizer documentation](http://centerforopenscience.github.io/exp-addons/modules/randomizers.html)
- 'expData' is an object with three properties (corresponding with the values from 'sequence'). Each of these objects has an 'eventTimings' property. This is a place to collect user-interaction events during an experiment, and by default contains the 'nextFrame' event which records when the 
  user progressed to the next **frame** in the 'sequence'. You can see which events a particular frame records by looking at the 'Events' tab in its [frame documentation](http://centerforopenscience.github.io/exp-addons/modules/frames.html). Other properties besides 'eventTimings' are dependent on 
  the **frame** type. You can see which properties a particular frame type records by looking at the parameters of the `serializeContent` method under the 'Methods' tab in its [frame documentation](http://centerforopenscience.github.io/exp-addons/modules/frames.html).  Notice that 'exp-video' captures no data, and that both 'exp-survey' **frames** capture a 'formData' object.
