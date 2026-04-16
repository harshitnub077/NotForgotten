"""Generate a sample PDF for testing ingestion."""
from fpdf import FPDF

def create_sample_pdf(filename="sample_concept_notes.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="Neural Networks and Gradient Descent Recap", ln=1, align="C")
    
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=(
        "Gradient descent is a first-order iterative optimization algorithm for finding a local minimum "
        "of a differentiable function. To find a local minimum of a function using gradient descent, "
        "we take steps proportional to the negative of the gradient (or approximate gradient) of the "
        "function at the current point.\n\n"
        "In machine learning, we use gradient descent to update the parameters of our model. Parameters "
        "refer to coefficients in Linear Regression and weights in neural networks. This relies on the "
        "Backpropagation algorithm, which calculates the gradient of the loss function with respect to "
        "the weights of the network."
    ))

    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="Attention Mechanism in Transformers", ln=1, align="C")
    
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=(
        "The self-attention mechanism allows the inputs to interact with each other and compute a "
        "representation of each input word that models the contextual meaning. In the transformer, "
        "self-attention computes a set of queries, keys, and values. It maps a query and a set of "
        "key-value pairs to an output, where the query, keys, values, and output are all vectors. "
        "The output is computed as a weighted sum of the values, where the weight assigned to each "
        "value is computed by a compatibility function of the query with the corresponding key."
    ))

    pdf.output(filename)
    print(f"✅ Created {filename}")

if __name__ == "__main__":
    create_sample_pdf()
