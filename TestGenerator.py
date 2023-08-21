import yaml
import re
import sys, os


#trova i parametri usati nelle api e li mappa per dichiararli nelle classe test
def generate_mapped_vars(swagger_data):
    vars = {}
    pattern = r'\{([a-zA-Z0-9_?]*)\}'
    #il problema è che non mappa le variabili facoltative con ?

    for path, path_data in swagger_data['paths'].items():
        matches = re.findall(pattern, path)

        for key in matches:
            if "?" in key:
                parametro = key.replace('?', '_optional')
            else:
                parametro = key
            if parametro not in vars.keys():
                vars[parametro] = '$this->' + parametro

    return vars

#sostituisce la stringa yml con una adatta per la classe PHP
def convert_api_path(api_path, mapped_vars):
    for variable, value in mapped_vars.items():
        prop = variable.replace('_optional', '?')
        api_path = api_path.replace(f'{{{prop}}}', value)
    return api_path

#ottiene il json che si aspetta con status code 200
def get_expected_response(method_data, status_code):
    exp_resp = {}
    for props, prop_data in method_data.items():
        if props == "responses":
            for response, resp_data in prop_data.items():
                if response==str(status_code):
                    data_response = resp_data["content"]["application/json"]["schema"]["properties"]
                    for key, value in data_response.items():
                        tipo = value["type"]
                        #fix: number non esiste nei wheretype laravel
                        if tipo == "number":
                            tipo = "double|integer"
                        exp_resp[key] = tipo

    return exp_resp

#ricava il nome del test laravel
def get_test_name_by_path(path):
    name = ""
    for i in range(2,len(path.split("/"))):
        test_name = f"""{re.sub(r'(?<!^)(?=[A-Z])', '_', path.split("/")[-i]).lower()}"""
        if "$" not in test_name and "api" not in test_name:
            if name == "":
                name = test_name + name
            else:
                name = test_name + "_" + name
        
    return name



#scrive i test per laravel
def generate_laravel_tests(swagger_file):
    with open(swagger_file, 'r') as f:
        swagger_data = yaml.safe_load(f)

    tests = []
    mapped_vars = generate_mapped_vars(swagger_data)

    for path, path_data in swagger_data['paths'].items():
        path = convert_api_path(path, mapped_vars)
        for method, method_data in path_data.items():

            
            test_name = get_test_name_by_path(path)

            expected_responses = get_expected_response(method_data, 200)

            expected_responses_keys = "\'" + '\', \''.join(expected_responses.keys())+"\'"

            expected_responses_types = ""
            for prop, type in expected_responses.items():
                expected_responses_types = expected_responses_types + f"\n\t\t\t\t\t->whereType('{prop}', '{type}')"

            check_success = ""

            if "success" in expected_responses.keys():
                check_success = "\t\t\t\t\t->where('success', true)\n"

            test = f"""\
    public function test_{method.lower()}_{test_name}() 
    {{
        $response = $this->json('{method.upper()}', "{path}");

        $response->assertOk()
            ->assertJson(fn (AssertableJson $json) =>
                $json->hasAll([{expected_responses_keys}]){expected_responses_types}
{check_success}
            );
    }}
    """
            tests.append(test)

    return tests, mapped_vars

if __name__ == '__main__':
    
    if len(sys.argv)<2 or len(sys.argv)>3:
        print(f"Usage: TestGenerator.py [required]swagger_yml_file [optional]output_laravel_test_name")
        sys.exit()
        
    swagger_file = sys.argv[1]
    output_name = "GeneratedTests"

    if len(sys.argv)==3: 
        output_name = sys.argv[2]

    if not os.path.isfile(swagger_file):
        print(f"il file {swagger_file} non esiste!")
        sys.exit()

    laravel_tests, mapped_vars = generate_laravel_tests(swagger_file)

    with open(f'{output_name}.php', 'w') as f:
        f.write("""\
<?php

//use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Testing\Fluent\AssertableJson;
use Tests\TestCase;

class """+output_name+""" extends TestCase
{

//use RefreshDatabase;

""")
        #scrive le variabili mappate
        for variable, value in mapped_vars.items():
            f.write(f"\tprivate ${variable} = '';\n")
            
        f.write('\n')
        
        #scrive i test 
        for test in laravel_tests:
            f.write(test + '\n')
        f.write('}\n')
