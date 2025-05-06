import ollama
import sys


class NPCInterpreter:
    def __init__(self, file_path):
        self.npcs = []
        self.load_npc_file(file_path)
    
    def load_npc_file(self, file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Find all NPC declarations within the program
        remaining_content = content
        while "npc" in remaining_content:
            npc_start = remaining_content.find("npc") 
            # Using boolean flag logic to know when in quotes and knowing when you reach a quotation
            open_braces = 0
            npc_end = npc_start
            in_quotes = False
            quote_char = None
            
            for i in range(npc_start, len(remaining_content)):
                char = remaining_content[i]
                
                # Handle quotes to avoid counting braces inside quotes
                if char in ['"', "'"] and (not in_quotes or quote_char == char):
                    #Once it reaches a quote it changes to True to let know we reached a quote
                    in_quotes = not in_quotes
                    #Sets char to '"' once verified that it is in quotes
                    quote_char = char if in_quotes else None
                
                if not in_quotes:
                    if char == '{':
                        open_braces += 1
                    elif char == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            npc_end = i + 1
                            break
            
            if open_braces != 0:
                print("Error: Unbalanced braces in NPC initialization")
                break
            

            npc_block = remaining_content[npc_start:npc_end]
            remaining_content = remaining_content[npc_end:]
            
            #Parsing the block
            self.parse_npc_block(npc_block)
    
    def parse_npc_block(self, npc_block):
        #Finds first quotation within the String for the npc initialization
        name_start = npc_block.find('"', npc_block.find("npc") + 3)
        #Finds the ending quote for that given String so it doesn't recheck first quote
        name_end = npc_block.find('"', name_start + 1) 

        if name_start == -1 or name_end == -1:
            print("Error: Could not find NPC name")
            return
        #Inclusive for beginning so +1, but excludes at the end
        npc_name = npc_block[name_start + 1:name_end] 
        
        #Attaining the traits
        traits = []
        traits_start = npc_block.find("[", npc_block.find("traits"))
        traits_end = npc_block.find("]", traits_start)
        if traits_start != -1 and traits_end != -1:
            traits_string = npc_block[traits_start + 1:traits_end]
            traits = [t.strip() for t in traits_string.split(",")]

        
        dialogue_start = npc_block.find("{", npc_block.find("dialogue"))
        dialogue_end = self.find_matching_brace(npc_block, dialogue_start)
        dialogue_block = npc_block[dialogue_start + 1:dialogue_end]
        

        memory = None
        memory_keyword = "memory"
        if memory_keyword in npc_block:
            memory_pos = npc_block.find(memory_keyword)
            memory_start = npc_block.find('"', memory_pos)
            if memory_start != -1:
                memory_end = npc_block.find('"', memory_start + 1)
                if memory_end != -1:
                    memory = npc_block[memory_start + 1:memory_end]
        
        #Using a dictionary so it is easier to access the specific elements after parsing for responses and such
        npc = {
            'name': npc_name,
            'traits': traits,
            'memory': memory,
            'triggers': [],
            'interactions': [], #all of the dialogue
            'fallback': None
        }
        # Parse dialogue content
        self.parse_dialogue(dialogue_block, npc)
        
        self.npcs.append(npc)
    
    def find_matching_brace(self, text, start_pos):
        if text[start_pos] != '{':
            return -1
            
        open_braces = 1
        in_quotes = False
        quote_char = None
        
        for i in range(start_pos + 1, len(text)):
            char = text[i]
            
            if char in ['"', "'"] and (not in_quotes or quote_char == char):
                in_quotes = not in_quotes
                quote_char = char if in_quotes else None
            
            if not in_quotes:
                if char == '{': 
                    open_braces += 1
                elif char == '}':
                    open_braces -= 1
                    if open_braces == 0:
                        return i
        
        return -1
    
    def parse_dialogue(self, dialogue_block, npc):
        remaining = dialogue_block
        
        #Checks for all events in dialogue 
        while "on" in remaining:
            on_pos = remaining.find("on")
            #Ensuring proper 'on'
            if on_pos > 0 and remaining[on_pos-1].isalnum():
                remaining = remaining[on_pos+2:]
                continue
                
            # Looking for indices to substring important values
            event_start = remaining.find('"', on_pos)    
            event_end = remaining.find('"', event_start + 1)
                
            line_start = remaining.find('"', event_end + 1)
                
            line_end = remaining.find('"', line_start + 1)
                
            arrow_pos = remaining.find("->", line_end)

                
            action_start = arrow_pos + 2
            action_end = action_start
            while action_end < len(remaining) and remaining[action_end].isalnum():
                action_end += 1
                
            # Check if this is a proper trigger and not part of an interaction
            # Look backwards from on_pos to see if "with" exists
            with_pos = remaining.rfind("with", 0, on_pos)
            if with_pos != -1:
                # Check if there's no semicolon or other statement separator between with and on
                if not any(c in remaining[with_pos:on_pos] for c in ";}"):
                    # This is likely part of an interaction, not a trigger (not npc to user)
                    remaining = remaining[on_pos+2:]
                    continue
            
            event = remaining[event_start + 1:event_end]
            line = remaining[line_start + 1:line_end]
            action = remaining[action_start:action_end].strip()
            
            npc['triggers'].append({
                'event': event,
                'line': line,
                'action': action
            })
            
            remaining = remaining[action_end:]
        
        # Parse interactions (with "target" on "event": "line" -> action)
        remaining = dialogue_block
        while "with" in remaining:
            with_pos = remaining.find("with")
                
            # Check if this is part of a word
            if with_pos > 0 and remaining[with_pos-1].isalnum():
                remaining = remaining[with_pos+4:]
                continue
                
            # Look for the pattern format
            target_start = remaining.find('"', with_pos)

                
            target_end = remaining.find('"', target_start + 1)
            
                
            # Check for "on" after target
            on_pos = remaining.find("on", target_end)
             
            event_start = remaining.find('"', on_pos)
                 
            event_end = remaining.find('"', event_start + 1)
                 
            line_start = remaining.find('"', event_end + 1)
                
            line_end = remaining.find('"', line_start + 1)
            
            arrow_pos = remaining.find("->", line_end)
            
                
            action_start = arrow_pos + 2
            action_end = action_start
            while action_end < len(remaining) and remaining[action_end].isalnum():
                action_end += 1
                
            target = remaining[target_start + 1:target_end]
            event = remaining[event_start + 1:event_end]
            line = remaining[line_start + 1:line_end]
            action = remaining[action_start:action_end].strip()
            
            npc['interactions'].append({
                'target': target,
                'event': event,
                'line': line,
                'action': action
            })
            
            remaining = remaining[action_end:]
        
        # Parsing the prompt for generating a response
        fallback_pos = dialogue_block.find("fallback")
        if fallback_pos != -1:
            ai_pos = dialogue_block.find("ai", fallback_pos)
            if ai_pos != -1:
                prompt_start = dialogue_block.find('"', ai_pos)
                if prompt_start != -1:
                    prompt_end = dialogue_block.find('"', prompt_start + 1)
                    if prompt_end != -1:
                        prompt = dialogue_block[prompt_start + 1:prompt_end]
                        #Insert into dictionary
                        npc['fallback'] = {
                            'prompt': prompt
                        }
    
    def find_npc(self, name):
        for npc in self.npcs:
            if npc['name'].lower() == name.lower():
                return npc
        return None
    
    def process_input(self, npc_name, player_input, is_npc_interaction=False):
        npc = self.find_npc(npc_name)
        if not npc:
            return f"NPC {npc_name} not found.", None
        
        # Check triggers for appropriate event word
        if not is_npc_interaction:
            for trigger in npc['triggers']:
                if trigger['event'].lower() in player_input.lower():
                    return trigger['line'], trigger['action']
        
        # Check interactions with other NPCs
        for interaction in npc['interactions']:
            if interaction['event'].lower() in player_input.lower():
                target_npc = self.find_npc(interaction['target'])
                if target_npc:
                    response, _ = self.process_input(
                        target_npc['name'],
                        interaction['line'],
                        is_npc_interaction=True
                    )
                    return f"{interaction['line']} (to {target_npc['name']}: {response})", interaction['action']
                else:
                    return f"{interaction['line']} (but {interaction['target']} isn't here)", interaction['action']
        
        # Using fallback in the event that you respond with a unique dialogue that doesn't have pre-existing answer
        if npc['fallback']:
            prompt = npc['fallback']['prompt']
            traits = ", ".join(npc['traits'])
            memory = npc['memory'] if npc['memory'] else "No specific memory"
            
            
            context = "responding to a player" if not is_npc_interaction else f"responding to another NPC ({player_input})"
            
            full_prompt = f"""You are {npc['name']}, a character with these traits: {traits}.
            Your memory context: {memory}.
            Current situation: {context}.
            The message was: "{player_input}".
            {prompt}
            Respond concisely in character."""
            response = ollama.generate(
                    model='llama3',
                    prompt=full_prompt,
                    options={'temperature': 0.7}
                )
            return response['response'], 'ai_response'
        

    def list_npcs(self):
        return [npc['name'] for npc in self.npcs]


# Menu Screen
if __name__ == "__main__":
    interpreter = NPCInterpreter(sys.argv[1])
    
    while True:
        print("\nAvailable NPCs:", ", ".join(interpreter.list_npcs()))
        npc_name = input("\nWhich NPC do you want to interact with? ").strip()
        if not npc_name or npc_name.lower() == 'quit':
            break
            
        npc = interpreter.find_npc(npc_name)
        if not npc:
            print(f"NPC {npc_name} not found.")
            continue
            
        print(f"\nYou are now approaching {npc['name']}...(Type 'quit' to exit, 'switch' to change NPC)")
        events = [trigger['event'] for trigger in npc['triggers']]
        print(f"Options: {', '.join(events)}")
        if npc['memory']:
            print(f"(Note: {npc['memory']})")
        
        while True:
            player_input = input("\nYou: ").strip()
            if player_input.lower() == 'quit':
                break
            if player_input.lower() == 'switch':
                break
                
            response, action = interpreter.process_input(npc_name, player_input)
            if action and action == 'ai_response':
                print(f"{npc['name']}: {response}")
            elif action:
                print(f"{npc['name']}: {response} -> {action}")
