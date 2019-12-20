# Returns either Integer or Exception
def string_to_float(value):
    if value == "":
        raise ValueError("String given was empty")
    try:
        return float(value)
    except:
        raise ValueError("String given can not be transformed")

