---
title: "Are We Thinking Correctly About AI Intelligence?"
source_type: "article"
origin: "web"
date_ingested: "2026-08-20"
domain: "ai"
status: "raw"
topics: 
  - "artificial-intelligence"
date_published: "2026-08-20"
source_id: "SRC-20260820-0001"
canonical_url: "https://www.quantamagazine.org/are-we-thinking-correctly-about-ai-intelligence-20260820/?print=1"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: Are We Thinking Correctly About AI Intelligence?
domain: ai
source_type: article
origin: url
canonical_url: https://www.quantamagazine.org/are-we-thinking-correctly-about-ai-intelligence-20260820/?print=1
topics:
  - artificial-intelligence
date_published: 2026-08-20
---

<!-- topic_slug: artificial-intelligence -->

<!-- notes: Transcript from Podcast -->

View Original Article
            Print / Save

        The Joy of Why

Are We Thinking Correctly About AI Intelligence?

        By

            Steven Strogatz

                    and

                Janna Levin

August 20, 2026

            Computer scientist Melanie Mitchell discusses why artificial intelligence doesn’t “think” or “reason” like humans, and how we can create better methods for measuring machine cognition.

                    Read Later

Chanelle Nibbelink for Quanta Magazine

Introduction

                      Authors

Steven Strogatz

Podcast Host

Janna Levin

Contributing Columnist

August 20, 2026

                    View PDF/Print Mode

                            artificial intelligence

                            computer science

                            deep learning

                            large language models

                            machine learning

                            natural language processing

                            neural networks

                            The Joy of Why

                    All topics

When an LLM answers a question, is it reasoning like humans, or just producing text that looks like reasoning? The distinction isn’t just philosophical, this determines what we can trust AI to do, how closely we need to supervise it, and ultimately what its real-world impact will turn out to be.

Melanie Mitchell at the Santa Fe Institute argues that we lack adequate methods for measuring machine cognition, and that AI is a form of “alien intelligence” that operates through non-human cognitive mechanisms. In this episode of The Joy of Why, Mitchell tells Steven Strogatz how methods that psychologists use to study cognition in other kinds of “alien intelligence” — babies and animals — can be adapted to probe AI, and she lays out six principles for better assessing machine cognition. Their conversation ranges from the challenge of interpreting what’s happening inside these systems, to recent AI-assisted breakthroughs in mathematics, to why a math-performing horse from the early 1900s offers a cautionary tale for how we assess intelligence.

Listen on Apple Podcasts, Spotify, TuneIn or your favorite podcasting app, or you can stream it from Quanta.

            All episodes

        Your browser does not support the audio element.

                    00:00
                    /
                    52:09

                    APPLE

                    SPOTIFY

Transcript

[Music plays]

STEVE STROGATZ: I’m Steve Strogatz.

JANNA LEVIN: And I’m Janna Levin.

STROGATZ: And this is The Joy of Why.

LEVIN: A podcast from Quanta Magazine where we explore some of the biggest unanswered questions in math and science today.

STROGATZ: Well, hello, hello. This is unsurprisingly yet another show about AI.

LEVIN: I’m telling you, it’s a topic people can’t seem to get enough about, and I’m becoming reluctant to pontificate anymore. It’s changing too quickly.

STROGATZ: It’s true. It is moving very fast. Anything we say could be obsolete by next week.

LEVIN: Oh yeah.

STROGATZ: As we speak, it’s July 23rd, 2026.

LEVIN: And it feels different to me than it did in July 23rd, 2025, that’s for sure.

STROGATZ: Mmm. That’s actually relevant, this talking about timelines, because our guest today, Melanie Mitchell, who is a cognitive scientist and computer scientist at Santa Fe Institute, is someone that we had on the show previously. She and I spoke about five years ago, and that is before ChatGPT.

LEVIN: Right. And was she interested in AI then?

STROGATZ: Oh, yes.

LEVIN: Okay, so it wasn’t just cognitive science.

STROGATZ: Absolutely. I, I mean, yes, I should say Melanie has been thinking about AI for a long time, and she’ll tell us about that. But the thing that’s gonna be so interesting, I feel, for us to discuss today is, um, Melanie’s point of view, which is to think about the problem of AI from the standpoint of fields like developmental psychology. Like, how does a baby or a young child get to be as intelligent as they soon become?

LEVIN: Oh, I think that’s so interesting ’cause we’re so excited about the artificial mind when we have very little comprehension of the human mind.

STROGATZ: Exactly.

LEVIN: Right, so we’re trying to skip a step.

STROGATZ: Well, that’s right. And not just human mind, but also animal minds, right? So there’s the field of comparative psychology where we look at intelligence in birds or dogs or dolphins, whatever. Um, we have a lot to learn about thinking about intelligences other than our own adult human intelligence.

LEVIN: Yeah, and this idea that we’re going to somehow simply understand a mechanism to generate an artificial intelligence when we, again, don’t understand the mechanism that brings a baby to have its level of intelligence when it’s born or when it’s developing. I mean, I think that’s really interesting to combine those two. So I’m looking forward to this one.

Melanie Mitchell

STROGATZ: Well, great. So then let’s dive in with Melanie Mitchell. Here she is.

[Music plays]

STROGATZ: Hi there, Melanie.

MELANIE MITCHELL: Hey, Steve.

STROGATZ: Very excited to see you again. This is gonna be fun. We talked a few years ago back when this show was called The Joy of X, and I think you may be our first return champion.

MITCHELL: Oh boy, I’m honored.

STROGATZ: Well, you should be. And, I have you back because so much feels like it’s changed in artificial intelligence. We talked, I think it was maybe 2021, and ChatGPT tidal wave hit the world at something like November of 2022. Is that right?

MITCHELL: That’s right.

STROGATZ: So everybody knows that AI is everywhere. We seem to be talking about it. People are worrying about it. Some people are excited about it. It’s certainly very widely used. I suppose I’d like to start by asking, what has surprised you the most about the past few years?

MITCHELL: Oh, wow. So much has surprised me. Just the thought that we could get to where we are now just by training these models on huge amounts of human-generated language and images and so on. I never would’ve dreamed it. So I’ve just been really surprised by what’s happened in AI. Also just the kind of polarized reaction that appeared in the AI community and society at large, I think, has been a little surprising to me, too.

STROGATZ: Polarized in terms of, like, sometimes people will distinguish AI doomers and AI optimists. Is that the kind of thing you’re talking about?

MITCHELL: There’s that dimension, then there’s the dimension of people who believe that AI is smarter than humans and people who think that it’s far, far from being anywhere near human-like intelligence. I guess related to that is sort of the love-it and hate-it. And these are separate dimensions, but maybe they’re correlated.

STROGATZ: Well, and right, and the love-it and hate-it can be also tied to things like the impact on the environment versus, you know, the economic prosperity for certain companies, but then again, what about job loss? There’s so many dimensions to this.

MITCHELL: Oh, there’s so many, yeah.

STROGATZ: But the thing that I really wanna focus on with you today is complex systems, cognitive science, artificial intelligence. You have a lot of different hats but I’m really very curious about the work that you’ve been doing to look at AI through the lens of either developmental psychology, like the way that we try to think about the alien intelligence of human babies, or comparative psychology with the alien intelligence of our pet dogs or smart birds or dolphins or that kind of thing. I mean, it’s a really interesting take on this alien intelligence of AI.

MITCHELL: Yeah. Many people have described AI as an alien kind of intelligence ’cause it’s very different from humans, even though it’s been trained on human language and books and everything on the internet and so on. But the way that these systems work, the way that they learn, the way that they reason, the way they do what they do is just really different from the way humans do it.

And this theme was actually picked up by people in developmental psychology, especially, Mike Frank at Stanford, who wrote this paper about how AI people should take some inspiration from the study of babies and young children, developmental psych. And then other people have extended that to, what about animal intelligence? And I guess one of the things that people in cog sci have been urging is that people in AI actually adopt some experimental methodologies that would make AI more like a science.

STROGATZ: Yeah, I really like this point of view, and I think it may not be so familiar to our listeners. I have to admit it wasn’t that familiar to me. You know, I never studied cognitive science, or never took a course in developmental psychology, and people in those fields have been thinking about these issues for… Well, I don’t know. You tell me.

MITCHELL: Yeah, at least 100 years.

The thought that we could get to where we are now just by training these models on huge amounts of human-generated language and images… I never would’ve dreamed it.

STROGATZ: Yeah, 100 years now. Wow. And I was thinking on the way over we constantly talk about AI as a black box. That we can’t read the weights on the neurons very easily, or even if we can, we don’t know what they tell us. But for that matter, couldn’t you say that our own intelligence is in a lot of ways a black box?

MITCHELL: Absolutely. I mean, we have different ways to penetrate the black box. One is neuroscience, where we actually stick probes into neurons, or we use fMRI or other imaging techniques. There’s also psychology, where you actually look at just the behavior of a person or an animal, and try and infer from that underlying mechanisms.

And those two traditions have, for a long time, been quite separate. But the field of cognitive science tried to integrate them, and originally, the field of cognitive science also included AI. Somehow that integration didn’t work.

STROGATZ: You mean it didn’t catch on sociologically, or what do you mean?

MITCHELL: You know, originally it was thought we’re going to program them the way that humans work. And there was a very close connection between human psychology and people trying to build human psychology into AI. And then that actually didn’t yield success in AI the way that we’ve seen neural networks and learning from data rather than trying to program it in.

STROGATZ: I see.

MITCHELL: And neural networks itself was originally inspired by neuroscience, but the way that neural networks work today has diverged considerably from that original inspiration. So I think the field of machine learning has gone much more in the direction of statistics, which is quite separate from how cognitive science works.

STROGATZ: So at this point, I guess I’d like to talk a bit about benchmarks, because they do seem to be a big part of the discussion broadly in society these days. There was something that got a lot of people chattering in the world of math. One of the latest frontier models did something that looked like a kind of creativity, solved an old, longstanding math problem one of the problems that Paul Erdős, the great, Hungarian mathematician, he left lots of problems for people to think about, and one of them that they call the unit distance problem was recently solved in a very clever way by AI, and it involved putting two parts of math together in a way that hadn’t really been tried before. And so I bring that up because the last time we spoke, we were talking about an old AI that was learning to play some Atari game, or something. And you talked about how it was so good at playing, but then if you move the paddle a couple pixels up or something, it had to relearn all over again. It didn’t know how to play the slightest variation on the original game.

So the thing you said at the time that stuck with me: “The strange thing is that these machines don’t seem to be able to transfer their brilliance to any other domain than the one they’ve been trained on.” So that was five years ago. Now I guess I wonder, what do you think? Is that still true?

MITCHELL: Yeah, I mean, that particular model was not a large language model. It was a specific model to play the Atari game. Whereas now we have large language models that are trained on everything. So in some sense, they don’t have to transfer anything. They’re already trained. But, people in AI or machine learning talk about things that are in distribution and out of distribution, and that means that is this thing that we’re asking the models to do similar to things that it’s seen in its training data, or is wholly different?

And I think it’s hard to know. We don’t know what it’s been trained on. The model that’s solving these problems has certainly been trained on a lot of math because there’s a lot of math out there on the internet. It’s been trained on textbooks. It’s been trained on all of Steve Stogatz’s videos that are on YouTube. And these models are pretty good at taking things from one area and putting them together with another area.

But, you know, I don’t know how to talk about this notion of transfer when something’s been trained on everything, especially in a field like math.

STROGATZ: Huh.

MITCHELL: Where you know, “trained on everything” I think has some meaning in a way. If you say it’s been trained on everything that has to do with being human, clearly that’s not the case. But if you say it’s been trained on everything having to do with math or with code, I don’t know. Is all of mathematical knowledge out there in some kind of textual or video format?

The way that these [AI] systems work, the way that they learn, the way that they reason, the way they do what they do is just really different from the way humans do it.

STROGATZ: Well, you’re asking me. I, so the thing that is roiling our community in math lately as we try to make sense of what just happened is we used to think, “Okay, these machines are very good at searching,” or, “These programs are good at searching big spaces.” They have a tremendous amount of knowledge because, as you say, they’ve ingested the whole internet and the Library of Congress, and anything you can read, they’ve read.

So anything where knowledge and the ability to search and to compute very fast and to not forget, all that, that plays into their strength. But the, but to spot a connection between different branches that hadn’t been noticed before and to exploit that to solve a longstanding problem, if a human being did that, we would consider that an aesthetic high point.

You know, mathematicians love it when an idea from topology gets used to solve a problem in geometry, or when an idea from algebra helps. But then again, maybe it’s sort of easy. If you know everything that’s been done and you can look for a lot of possible connections, maybe you’ll occasionally get lucky. So that’s what it sort of seems like happened here.

MITCHELL: Yeah. No, I think that’s right. I don’t… You know, who knows how it happened because we can’t really look at the innards of the- these models very well for many reasons. But it is creative to bring two unexpected things together and have something that’s actually working. I consider that creative. But, it sort of reminds me in a way, there was a math discovery program way back in the ‘70s maybe done by this guy, Douglas Lenat. It was called EURISKO, I think. And basically it was trying to find new ideas in math. And it explicitly tried to bring together things and stick them together, and it would generate hundreds and hundreds and hundreds and hundreds of these things.

Most of them were just junk, but occasionally it would come up with something interesting. A human had to go in and look and say, “Is this interesting?” The machine couldn’t figure it out itself. So how much of that is going on here? I don’t know. I think here the difference is that the machine obviously is at a much bigger scale, and I don’t know how many tokens of reasoning trace that it generated in the course of solving this problem, and how many kind of wrong paths it went down, and how it figured out that it was on the right path. I mean, these are things that I think are part of the science of AI that not enough people are kind of pursuing right now.

STROGATZ: Yeah, let’s get into that now because that’s really where I wanted to go with you. It’s a nice phrase, the science of AI. I’d like to encourage people to look at this article of yours, Melanie, about the six principles to assess cognitive capacity of AI. But just, as a teaser, could you enunciate what are those six and say a little about them?

MITCHELL: Sure. So the first one is to be aware of your own anthropomorphic cognitive biases. So we tend to project human likeness onto things that talk to us in fluent English. So people very much think that these models have human-like qualities when maybe they actually don’t.

The second one’s a very common sense one for scientists. Be skeptical of hypotheses and develop control experiments. That’s just like Science 101, although I’m not sure how often it’s really followed through in science. People tend to like their own hypotheses.

The third is to develop novel variations of your stimuli or your benchmark items in order to test robustness and generalization.

Uh, the fourth one is these systems don’t have to be black boxes. You can probe them in many different ways and we need more people who are very curious about why they’re getting the results that they do get.

Fifth principle is to consider performance versus competence, sort of what you can show that you can do versus what you actually can do, and in the paper I give some examples of that.

The sixth is to analyze failure types and to embrace any negative results. We tend to put papers with negative results in a drawer and forget about them, but actually they can be incredibly enlightening.

STROGATZ: We all have very direct experience with number six, don’t we? When we see the hallucinations, it starts to make you wonder what’s really going on with these systems, and it’s true you learn a lot from the errors.

MITCHELL: Yeah, people celebrate their positive results and they try to explain away their negative results, but it’s important to really understand what’s going on by looking at where it fails.

STROGATZ: So one example that you give in your article, this is not about AI, but this is about the kind of lesson from biology or from psychology that subtle things can be happening that you need to have an alert and skeptical mind to notice what might really be going on. So could you just regale us with the old story of Clever Hans?

MITCHELL: So Clever Hans was a horse who lived in the early 1900s in Germany. And Clever Hans was able to answer arithmetic questions. So you’d say like, “What’s 14 plus 12?” And he would tap his hoof that many times. Looked like a genius horse. And people including many scientists living back then, were very convinced that this was an animal who could do mathematics, who could count, who could reason about simple problems in the way that humans do.

And people were very excited. But then a psychologist, named Oskar Pfungst, came along and said, “Well, let’s do some controlled experiments here,” this notion of controlled experiments you know in psychology being kind of a new idea, I think. And let’s see what happens if he can’t see the person who’s asking the question.

How can we trust the results of these experiments and studies that are done that show that AI can do all these different things?

STROGATZ: Okay

MITCHELL: And then he fails. And it turns out what he’s doing is he’s reading subtle cues on the face of the person who’s asking the question. It turns out that if the person who’s asking the question doesn’t know the answer already, he also fails.

’Cause what the person is doing is they’re reacting to his hoof taps, and when he gets to the answer, there’s some unconscious signal they’re sending that he’s reading. So he is a genius horse, just not at the things that people thought he was a genius at. Instead, he’s a genius at reading social signals in human faces.

STROGATZ: And so in this parable then, as far as like when we are impressed by something seemingly genius that AI is doing, what is our lesson? That, that we should be doing controlled experiments, or what?

MITCHELL: Right. So, an AI system was shown to be really good at reasoning about diagrams in scientific papers, let’s say, I think this is, actually a real example, and could answer questions about them. But then the control experiment was give the questions without showing the diagrams. Seems crazy, right? How could you answer questions about a diagram without seeing the diagram? And it turned out that the AI could do this task because somehow there was some kind of spurious association between the words in the questions and the correct answer.

STROGATZ: So that seems like a case of poor experimental design on whoever was doing the benchmark attempt in retrospect.

MITCHELL: In retrospect, and in retrospect this happens all the time in psychology and other fields, I’m sure too, poor experimental design. Experimental design is a very hard thing and there’s all kinds of confounding possibilities. So this is why the notion of replication in science became so important. If one group does an experiment and they get a result, we shouldn’t necessarily believe that result. That result might be due to some other aspect of their experimental design that wasn’t intended. That’s why it’s very important for independent groups to replicate studies. This isn’t something that people in AI do very much.

STROGATZ: No, and why not? Is it that the replication is not very glamorous because you’re coming in second like there’s no incentive. That’s true in all parts of science, right?

MITCHELL: Yeah. I think that’s true in all parts of science. But it’s also because I think most of AI research is done by people whose background is in computer science or a related field that’s not focused on experimental methodology. I’m a computer scientist. I never had to take a course in experimental methodology. No such course was ever offered to me in my department. It wasn’t seen as part of what computer science was all about, and I think that’s one of the things that’s lacking in today’s AI discussion. How can we trust the results of these experiments and studies that are done that show that AI can do all these different things?

[Music plays]

LEVIN: Fascinating. So it seems to me that there’s this cognitive science version of the interference of the observer that everyone talks about in quantum mechanics, right? The observer themselves is interfering with the experiment or the outcome of the experiment, and that is such an interesting role. Of course, this Clever Hans is very famous, and I agree that that is a very clever horse for being able to read the social cues.

But how interesting if this is also happening with AI, that it’s, it’s not just the role of the experimenter that’s interfering, it’s actually the role of the psychology of the experimenter that’s interfering.

STROGATZ: Yeah. It’s a whole dimension that many of us in the theoretical sciences and math don’t get trained in, as Melanie freely admits. You know, I never took a course in experimental design. You as a physicist, I assume you had to take some experimental physics, but…

We had a talk here at Santa Fe Institute from a philosopher who broke down understanding into 25 different types.

LEVIN: Yeah. It doesn’t really weigh in my actual work. It’s really not experimental. Yeah. So I would not be a very good architect of a good experiment.

STROGATZ: Well, and it seems like it is, something that’s a very live issue because these days the AI companies frequently use benchmarks to show how – well, to assess how – how far along are their systems on this quest for either artificial general intelligence or superhuman intelligence, that sort of thing. Or even just to out-compete the other AI companies. We would like to know what the capacities are of these new machine learning systems and other AIs.

LEVIN: Well, I think it might be that it’s just, I don’t think we really know how to evaluate human intelligence, or to really know what somebody’s doing when they’re thinking. I don’t think we know about ourselves. I don’t think we can self-report very well. I can’t say to you, “Oh, this is how it’s working in here right now as I’m constructing this sentence. I listened to it, and this was the process.” I don’t know, right? It’s just natural. It just comes out. And I’m not that privy to the inner workings, and I feel the AI similarly. A lot of people have said, I’ve had conversations on our show before with other cognitive scientists and computer scientists and they say it’s really hard for the AI to answer questions, ’cause a lot of people say, “Why don’t you just ask it?” And it can’t self-reflect either in an accurate way.

STROGATZ: This whole thought, the mystery of the black box. We use the term black box so often for the AI, but of course, our own intelligence is a black box, not just from mine to you, but even me to myself, as you’re emphasizing. But it makes me wonder if there’s a role for magicians because, you know, magicians or sleight-of-hand people are so good at showing us our own psychophysical limitations. How easily we’re fooled, or the sorts of cognitive errors we tend to make, and there are people who are analogous to the magicians who show the deficits and common sense of the AIs, right? They’re sort of playing games that are almost like magic tricks on the AIs. I wonder how revealing those will be, you know, in a serious scientific way.

Well, Melanie has a lot more to say about the depth of AI cognition and understanding, and also how it might change whole fields of science, including math. We will be hearing more about that after the break.

[Music plays]

STROGATZ: Welcome back to The Joy of Why. We’re joined today by Santa Fe Institute computer scientist Melanie Mitchell.

STROGATZ: You have been a college professor for much of your life. When you’re working with students they can get the answers right, but as you start to probe what they actually understand, you start to realize that they might be getting the right answers for the wrong reasons. They don’t really know what they’re doing, and that’s important if you wanna be a helpful teacher. This brings up another point: competence versus performance. Can you expand on this idea and, what would it mean in the AI context?

MITCHELL: So competence versus performance is kind of an old distinction from psychology and linguistics. The idea is that you might have the competence for a particular cognitive capacity, but there might be some reasons why you can’t perform the task that I’m giving you. Like they have the competence, they could solve the problems, but they’re just emotionally frozen. There’s some performance block.

But then there’s the other way around, which is performance without competence. So if the student in your office hours, say, had memorized a problem from the textbook and the solution, but they didn’t understand the general principle, so if you gave them a slightly different version of the problem, they couldn’t do it. That’s performance without competence.

STROGATZ: Okay. So if we would say that we’re trying to work out ways of testing whether the AI understands, what would count as evidence? Suppose that, you’re an AI advocate who said that these new systems, because we’ve scaled them up or because we have some nice new architecture with world models or social models or whatever, we’ve now crossed a threshold where they actually understand. It’s not just that they can compute, they understand. What would count as evidence of understanding?

MITCHELL: Oh gosh. I hate to get pedantic about understanding, but there’s so many different meanings of it.

STROGATZ: Ah.

MITCHELL: We had a talk here at Santa Fe Institute from a philosopher who broke down understanding into 25 different types.

STROGATZ: Aha. I didn’t know what I was getting myself into with the question.

I think it’s almost like a fallacy that if an AI system can do a bunch of tasks, it can do the job of a person that is associated with those tasks.

MITCHELL: So there’s like P understanding and G understanding and there’s this very long typography of understanding. And I’m not sure there is any sort of single notion of real understanding. One of the recent things I and my collaborators have been working on is looking at different dimensions of understanding. One example is you can get one of these language models or chatbots to generate a story. Just generate a short story about something, and they will. They’ll generate a very beautiful little coherent short story. But then if you start asking them questions about the story, they will often will fail in weird ways.

STROGATZ: Hmm.

MITCHELL: even though they generated it. And I think the same thing is true in a lot of different tasks that they understand along one dimension but not along another dimension. And in some sense deep understanding might be just you understand across many different of these dimensions.

STROGATZ: Aha. That sounds like a promising direction. Let’s talk about tasks a little more, because that’s a phrase or a term that I’ve seen in some of your writing, the phrase, the tyranny of tasks. What’s that about?

MITCHELL: I first heard that, from Shannon Vallor, a philosopher. The idea is that in AI, the world is divided in terms of tasks. So when we think about what AI systems can do, people say, “Oh, they can make summaries. Let’s test their ability to summarize articles.” Or, “Let’s test their ability to answer questions about diagrams” or I don’t know, some other benchmark.

STROGATZ: Well, I mean, these days, they’ve been benchmarked a lot on International Mathematical Olympiad, very hard high school problems, then there were research level problems. Now there’s open problems that are unsolved in math. These are all like three levels of math benchmarks that are out there.

MITCHELL: Right, their capabilities are defined in terms of these benchmarks. You know, one benchmark might be the bar exam for law students, and they do really well on the bar exam. And so we say, “Oh, lawyers, you should be afraid. Your job is threatened because these AI systems are as getting as good as you are.” Uh, But the way that we’re defining that is by looking at how well they do on a specific set of questions or a task. And jobs as a whole are not the same as just one independent task after another. This is, I think it’s almost like a fallacy that if an AI system can do a bunch of tasks, it can do the job of a person that is associated with those tasks.

So just one example of this. So there’s a famous quote from Geoffrey Hinton, where he said something like, “AI systems are incredibly good at diagnosing or interpreting radiology images. Nobody should go to school anymore to be a radiologist. AI is gonna take all the jobs within five years.”

Well, that was 2016. That was 10 years ago. Now we actually have a shortage of radiologists. I don’t know if that’s because he said that, but uh, it turns out that even though AI systems can beat human doctors on these benchmarks, that’s not the same as doing this job out in the real world, which is much more open-ended, which is not just a series of well-defined tasks.

STROGATZ: Still, it does leave you wondering, like in the case of radiology, you could imagine if they are really good at that task, then what’s left for the human radiologist? Should we still be in that part of the game? Like in my own world of math, you know, if they’re very good at proving theorems, but they’re not so great yet at coming up with new concepts, or as we sometimes speak of it, theory building, right? There’s this big distinction between problem-solving and theory building. So is it that we’re sort of gonna find our niche, that we can do the parts that they don’t do? So like in the case of radiology, they have the open-ended part but not the scan reading part? I guess that’s what I’m wondering.

MITCHELL: Yeah.

STROGATZ: Is that how it’s gonna go?

MITCHELL: Maybe. I wouldn’t be at all surprised if jobs like yours change quite a bit because of these new tools. These are going to become incredibly useful tools for mathematicians. So it might change your job. Just like when personal computers came out, but there’s a fantastic book by um, George Lakoff and Rafael Núñez about math and where ideas in math come from, via metaphors. And they feel that human embodiment is a very important part of understanding and mathematics.

I don’t think that solving all the Erdös problems means that the average person has to fear for their job.

STROGATZ: Exactly. I think that’s our only hope ’cause right now they the machines don’t have great embodiment. And you’re right, that a lot of great ideas in math are inspired by experience with the world. And that’s what I was gonna say about applied math, that I feel like that’s even more so than pure math, where we get so much inspiration from nature and from engineering and society and all that, that I think we have a lot more chance of being useful as humans in applied math.

But I do think pure math will expire before applied math does, and maybe neither will. Maybe we’ll just keep going forever. What does it look like to you? I mean, math is often thought of as some kind of gold standard like, the AI companies have a lot of use for math, right? They can demonstrate how good their systems are ’cause they can verify that they’ve solved a problem or not.

MITCHELL: Well, that’s a big question I have, which is, suppose that your prediction comes right and math, pure math expires in some sense for humans. What does that mean for other fields? Does that mean that these machines are on their way to taking over everything? Or is it more like 1997 or whatever it was that Deep Blue beat Kasparov and that actually beating the best human at chess did not necessarily mean that was gonna go anywhere in other fields.

STROGATZ: I don’t know. What do you think? It feels to me like science is much more open-ended than math in that respect.

MITCHELL: Yeah, I believe that. I don’t think that solving all the Erdos problems means that the average person has to fear for their job.

STROGATZ: Okay, now we have many different things on the table at that point. But even just in the world of pure brainiacs, whether it’s scientists or mathematicians, just the fact that biology there are so many things to be measured, we have so much data that we could collect that we haven’t collected, so many new ways of observing. I mean, that seems very inexhaustible to me compared to math.

MITCHELL: I agree. And even in physics, I think, which is maybe closer to math, there’s so much you know, open-ended questions that aren’t well-formulated, that don’t have something like a proof that can be constructed.

STROGATZ: But so, I do feel like the hope for math is to continue to take inspiration from the real world. And von Neumann had said something like that too, that when math becomes too much art for art’s sake, when it drifts too far from the source, for him the source was nature or reality, if it becomes too far removed it becomes sterile, said von Neumann.

So I think this could be a a really good era for pure math if it starts taking more inspiration from nature. That’s been less so in the 20th and 21st century, but I think if we go back to that, we can probably eke out a few more centuries of human pleasure in math.

MITCHELL: I’ll just say there’s this dictum in AI which is that easy things are hard and hard things are easy.

STROGATZ: Right.

MITCHELL: And pure math is seen by humans as like the most exalted exhibition of intelligence and brilliance. It’s the hard thing, and yet we know that hard things are easier for machines and easier things are harder.

STROGATZ: Yep, and there’s the word soft also, right? In science, we talk about the hard sciences and the soft sciences, and the soft sciences of economics and psychology and anthropology, and those are the really hard ones.

MITCHELL: Right.

STROGATZ: Well, so if we meet again in five years.

MITCHELL: The Joy of Gamma, or something.

STROGATZ: Yes, The Joy of Omega by then, right. What do you hope we would understand about AI systems by then? Or what kinds of tests would we want to be able to do that we can’t do today?

MITCHELL: Yeah, I mean What I really hope will go well in the science of AI is this field called mechanistic interpretability, which is the neuroscience analog, where you’re actually looking at the activations and the weights and the, you know, all the messy innards of the system, and understanding at a higher-level sort of what they are doing.

There’s this dictum in AI which is that easy things are hard and hard things are easy.

These days, it’s kind of a smallish subfield where people are trying to develop tools that do that, analogous to things like fMRI or whatever. And I don’t think anybody’s really figured out exactly how to do this the right way yet, but I’m hoping that’s something that we can accomplish, and then we would have a genuine way of understanding sort of their limitations, what they can do, what they can’t do, what kinds of mistakes they’re likely to make, and maybe how to fix them.

STROGATZ: Interesting that you put your finger on that because the first time I became aware of you, it was in connection with that in a broad sense. So what I’m thinking of is back when you used to work on something that in the jargon was called GAs for CAs, genetic algorithms for cellular automata, you and Jim Crutchfield were looking at this problem of evolving algorithms that could solve a certain class of problems, hard computer science problems, and you were using this evolutionary algorithm to select better and better algorithms that kept improving through a kind of selection process.

But then the part that you did that I found so creative is once you’ve got a really good system, you looked at it in what felt to me like an analog of mechanistic interpretability. You tried to see what was making that system so smart, analyzing it in terms of particles that were colliding with each other according to certain rules in the diagrams. That’s, I don’t know if I’ve summarized it reasonably well, but it seems like this is a longstanding interest of yours.

MITCHELL: Yeah. that’s true. I hadn’t made that connection exactly, but that’s interesting.

STROGATZ: It is this, though. It’s interpretability.

It is interpretability. And it’s also, I think, in the field of complex systems, people talk about this notion of emergence.

STROGATZ: Yeah.

MITCHELL: And we thought of that as a kind of emergent computation. And I think these AI systems also have emergent computations that are not easy to find, but they’re there, and if we understood them better, we would understand how the system is actually working, doing what it does.

STROGATZ: Yeah, it’s an interesting attitude. It feels honestly to me very sweet and very old school. This hope that… Okay, you’re chuckling ’cause you see where I’m going. It’s a mean thing I’m saying, but this conceit that we with our limited minds can keep doing science, you know, and we’re gonna figure out how these AIs are doing what they’re doing, and that’s what our game will continue to be just like it always has been in science.

And I, the dark side of me, thinks our days are numbered to be able to do that as these gadgets get bigger and bigger. Who says we can keep doing science on them and figuring them out? What’s your reaction to that? We have nothing else to do. We have to try.

MITCHELL: That’s an interesting question. Um, why do we do science in the first place? I mean, you know, we do science ’cause we wanna solve problems. That’s one thing. But we also do science ’cause we’re driven to understand things.

STROGATZ: Yes.

MITCHELL: You see this in little children. They’re driven to understand. Often one of their first words is why. They ask it constantly. So I think that’s a human drive, and it’s hard to fight against that. And that’s why you and I both went into science, it’s important to us.

Now, I was a little despairing when I went to a panel discussion at a conference on the role of AI in science. And there were a bunch of famous people on the panel talking about how AI was going to revolutionize weather prediction, and genetics, and cosmology, and you name it. And I asked them at the end “Well, like, is this going to contribute to human understanding of the world?” And they’re like, “Why should we care about that?”

STROGATZ: Yeah. To me, this is the bifurcation that we’re all thinking about now. ’Cause science has this double-edged aspect, that it gives us pleasure, we like figuring things out, there is the joy of why, and as you say, it’s deep in our species. So yes, we’re curious, but then there’s the other side that for so long science has been this instrumental thing that helps us in technology and medicine.

And I guess the question I have, and I think a lot of us have, is will we continue to take pleasure in the joy of curiosity when we are no longer the best at solving the important problems? But let me ask you one last thing, for people who haven’t heard our earlier conversation, what was your draw to this field, and if you were starting out today, do you think you’d have the same kind of curiosity?

MITCHELL: Yeah, that’s a great question. When I was a child, I loved logic puzzles, like the knights and the knaves. The knights who always told the truth and the knaves who always lied. There’s a fun several books by Raymond Smullyan, a mathematician who wrote a bunch of puzzles in this genre that I absolutely loved.

Why do we do science? We do science ’cause we wanna solve problems. We also do science ’cause we’re driven to understand things.

When I got to college, I read Douglas Hofstadter’s book, Gödel, Escher, Bach, which was the real-world version of these in a way. I mean, he was talking about Gödel’s theorem and paradoxes in mathematical logic and how all this related to cognition and thinking and creativity and so on. And I was just completely blown away and that this is what I wanna do in my life. I didn’t exactly know what it was, but it seemed like it might be artificial intelligence. So I pursued Doug as an advisor and got to join his group, and was studying analogy via a new set of puzzles which were analogy puzzles. And, I was very entranced by all of that.

If I were that age today, I would be worried. In fact, I have a son who is getting a PhD in machine learning, and he wants to do research in machine learning, but he’s actually quite nervous that there will be no more roles for humans doing research in machine learning because AI will be doing all the research in machine learning and improving itself and so on and so forth. And I wonder if I’d think the same thing. I don’t know.

STROGATZ: Maybe we do have to revisit this in five years because we may know by then. Given how fast everything is going, who knows? I really appreciate your spending time with us. This has been wide-ranging, a little bit amorphous conversation, but it’s just wide open and I can’t think of a better guide to it. Thank you very much for joining us.

MITCHELL: Thanks, Steve. It’s been great.

[Music plays]

LEVIN: Hmm. Hmm. I, I just remember being a student and learning Newton’s laws for the first time, and then Kepler’s laws, which really make Newton’s laws beautiful, this application to the celestial cycles. I didn’t think, “Oh, I’m not the best at this, therefore I shouldn’t learn it.” Nor did I think, unless I one day become the best at this, I cannot feel pleasure or joy in my experience of acquiring this information.”

Of course, lots of people study things that other people already know and are better at. So I, I sort of wonder if maybe the AI will know things before us, but we will still need to acquire the understanding ourselves, and in that acquisition is a similar experience. Instead of maybe the AI will be a filter between us and interrogating nature directly, but we’ll still be acquiring, I don’t know, the knowledge and having that experience. I’m not sure. Maybe it’s all gonna pass us by.

STROGATZ: I– Well, let’s explore this a little more. I like especially your emphasis on not being the best, and how, in a way, unfraught that is. I, I learned as soon as I went to college what it means to not be the best. You know, this, this fixation with being the number one, especially in an age of optimization. There’s so many optimization algorithms. We talk about faster, cheaper. But in our own lives, very often we’re not the best. I’m certainly not the best tennis player. I love to play tennis. I’m not the best chess player, and I’m still happy to play chess. And try to be the best dad, but I may not be. But still, all these things are worth doing for their own sake, right? They give us pleasure.

I do feel very philosophical and almost religious about this. Like, we get a little time on Earth alive and, you know, these questions about AI do tap into questions about the meaning of life. What are we trying to do? If the meaning of life is that you’re gonna be the best in some domain or you’re gonna make a discovery that’s gonna change the world, then most people will have a meaningless life, and I just don’t wanna believe that’s the correct version of the meaning of life.

It was not for my dad. He didn’t even get to go to college. You know, he grew up in the Depression. That was not an option. His life was being a good parent and taking care of the people that bought shoes at the shoe store that he had. And he knew everyone’s shoe size in our little town, and he left a good name when he died. People remembered him well.

LEVIN: Right.

STROGATZ: So okay. What is that doing on our show here about science?

LEVIN: Well, I think that let’s say the meaning for some people of life has to do with acquisition, acquiring wealth. They’re gonna love this stuff, right? ’Cause there’s gonna be this new tool that simply leverages all kinds of buttons that they now have faster access to and can exploit and acquire more wealth.

There are people who found meaning in singing songs or writing poetry or being novelists or doing math, and, and I think all of those fields are a little more nervous, right? About reevaluating what the place is going to be for them and, and how to secure that place and how to think about it.

If I’m playing games of what may or may not happen, I mean, there is still a world in which AI is like a supercomputer, and we’ve talked about this before, Steve. Just ’cause a supercomputer can crunch all of these numbers, if it presents it to us as a string of symbols, even though it has, in some sense, an answer, it’s not a meaningful answer for us, and none of us value it.

We still, as human beings, have a very important role between us and a supercomputer rendering an image of a galaxy or looking at an image of a biomedical neural map. It hasn’t actually robbed scientists of their work. And so it might be that it really will continue to be a tool and not simply something that overtakes and discards us.

STROGATZ: Well, that’s the question, right? I think there are two plausible scenarios. One is that it continues to be a tool, and we always have some essential role in science and math at the cutting edge. The other option is, and actually in my heart I believe this is the case, that we will not be at the cutting edge, and that will happen very soon. And, so then what is the point?

Then I feel like it’s still meaningful, just like when I was in high school and I discovered things about math. They were discoveries to me. They were not discoveries to the world, you know? I think we may have to all settle for that. We’re not gonna be making genuine discoveries for the world.

The AIs will be doing that. I really do believe that’s gonna happen very soon. I may be wrong. I mean, there may be fundamental reasons why the AIs won’t be able to do that. For instance, they don’t have bodies, they don’t have social life, you know, there’s a lot… But I just think all that stuff will be solved before long. Anyway, what’s your take?

LEVIN: Well, I think there’s a difference between, making discoveries and understanding, and I guess that’s kind of what I mean in examples. In some sense, maybe the su- supercomputer made the discovery before the person did, but we still say the person did ’cause the discovery didn’t count as a discovery until they rendered it in a way that human beings could comprehend.

But, I honestly don’t know. I am not incredibly saddened or pessimistic, so I guess I would have to say that in my heart, intuitively, I am not terrified of this prospect. Maybe I should be, but maybe it’s just sort of a bliss of being naive and I’m just gonna wait for it to sneak up on me.

STROGATZ: There is one thing I think we can be very optimistic about and hopeful about, which is I think we’re gonna have a glorious golden age of science where we will understand, and discoveries by the AIs or by people in conjunction with AIs, that’s all gonna be happening in the next, whatever, five, 10, 15 years, and it’s gonna be a spectacular fireworks time for science. And I think that hopefully with any luck, we’ll be alive to see all that.

LEVIN: Yeah, there’s definitely going to be a transition period where people are moving it fast and furious, and they’re part of the story, and there’s great accomplishment, and it will be exciting to see. I know people, very accomplished, who are very excited about using it. Use it every day. They have multiple things going on, and they just feel like their productivity has doubled or more. And they’re excited, they’re enjoying themselves. I think there’s really nothing we can do but chime in and participate in this, at least, transition phase before we’re obsolete.

STROGATZ: Well, I’m getting choked up just thinking about it. Thanks, Janna. It’s always great to see you, and we’ll see you next time on The Joy of Why.

LEVIN: Thanks, Steve.

[Music plays]

Related:

                                    Melanie Mitchell Takes AI Research Back to Its Roots

                                    Is AI Reasoning Right for the Wrong Reasons?

                                    Why Do We Tell Ourselves Scary Stories About AI?

                                    The Computer Scientist Training AI to Think With Analogies

LEVIN: If you’re enjoying The Joy of Why and you’re not already subscribed, hit the subscribe or follow button wherever you’re listening. You can also leave a review for the show. It helps people find this podcast. Find articles, newsletters, videos and more at quantamagazine.org.

STROGATZ: The Joy of Why is a podcast from Quanta Magazine, an editorially independent publication supported by the Simons Foundation. Funding decisions by the Simons Foundation have no influence on the selection of topics, guests, or other editorial decisions in this podcast or in Quanta Magazine. The Joy of Why is produced by PRX Productions.

The production team is Caitlin Faulds, Jade Abdul-Malik, Genevieve Sponsler, and Merritt Jacob. The executive producer of PRX Productions is Jocelyn Gonzales. Edwin Ochoa is our project manager.

From Quanta Magazine, Simon Frantz and Samir Patel provided editorial guidance, with support from Samuel Velasco, Kit Sudol, Simone Barr, and Michael Kanyongolo. Samir Patel is Quanta’s Editor-in-Chief.

The episode art is by Chanelle Nibbelink and our logo is by Jaki King and Kristina Armitage. Special thanks to Garth Avery at the Cornell Broadcast Studio.

I’m your host, Steve Strogatz. If you have any questions or comments, please email us at [email protected]. Thanks for listening.

[Music fades]

                Share this article

Copied!

                    Newsletter

                    Get Quanta Magazine delivered to your inbox

                    Subscribe now

                      Authors

Steven Strogatz

Podcast Host

Janna Levin

Contributing Columnist

August 20, 2026

                    View PDF/Print Mode

                            artificial intelligence

                            computer science

                            deep learning

                            large language models

                            machine learning

                            natural language processing

                            neural networks

                            The Joy of Why

                    All topics

                Share this article

Copied!

                    Newsletter

                    Get Quanta Magazine delivered to your inbox

                    Subscribe now

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/domains/ai/source-manifest.json::SRC-20260820-0001
- Source path: /Users/erickperales/Projects/knowledge_base/raw/domains/ai/inbox/browser/are-we-thinking-correctly-about-ai-intelligence.md
- Canonical URL: https://www.quantamagazine.org/are-we-thinking-correctly-about-ai-intelligence-20260820/?print=1

