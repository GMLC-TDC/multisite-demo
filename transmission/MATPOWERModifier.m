classdef MATPOWERModifier
    
   properties
       MATPOWERModel 
   end
   
   methods
       %%  Read Model from JSON or m format %%
       function obj = MATPOWERModifier(config_file)
           obj.MATPOWERModel = obj.read_model(config_file);
       end
       
       function model = read_model(obj, case_name)
           if isempty(regexp (case_name,'.json'))
               model = loadcase(case_name); %% Load in built MATPOWER CASE
           else
               fid = fopen(case_name);
               raw = fread(fid,inf); 
               str = char(raw'); 
               fclose(fid); 
               model = jsondecode(str);
           end
       end
       
       %%  Wrtie MATPOWER Model to JSON format%%
       function write_model(obj, file)
           str = jsonencode (obj.mpc);
           fid = fopen(file, 'w'); 
           fwrite(fid, str);
           fclose(fid); 
       end 
      
   end
   
end