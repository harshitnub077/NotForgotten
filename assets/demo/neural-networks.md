# How Neural Networks Learn

## Artificial neurons

An artificial neuron is a simple computational unit that multiplies each input by a weight, adds the results together with a bias term, and passes the sum through an activation function. The weights determine how strongly each input influences the output, and the bias shifts the point at which the neuron becomes active. A neural network is a collection of these neurons arranged in layers, where the outputs of one layer become the inputs of the next.

## Activation functions

An activation function introduces non-linearity into a network. Without it, any stack of layers would collapse into a single linear transformation and could only model straight-line relationships. The sigmoid function squashes values into the range between zero and one, which makes it useful for probabilities but causes gradients to vanish for very large or very small inputs. The rectified linear unit, or ReLU, outputs zero for negative inputs and the input itself for positive inputs. ReLU is cheap to compute and keeps gradients alive, which is why it became the default choice in deep networks.

## Loss functions

A loss function measures how far the network's predictions are from the correct answers. Mean squared error is the average of the squared differences between predictions and targets, and it is commonly used for regression. Cross-entropy loss compares a predicted probability distribution with the true distribution and is the standard choice for classification. Training a network means searching for the weights that make the loss as small as possible.

## Gradient descent

Gradient descent is an optimisation algorithm that repeatedly adjusts the weights in the direction that reduces the loss most quickly. The gradient is the vector of partial derivatives of the loss with respect to every weight, and it points in the direction of steepest increase, so the algorithm takes a step in the opposite direction. The learning rate controls the size of each step. A learning rate that is too large makes training unstable and can cause the loss to diverge, while one that is too small makes training painfully slow.

Stochastic gradient descent estimates the gradient from a small random batch of examples rather than the entire dataset. The noise in these estimates speeds up training and can even help the optimiser escape poor local minima. Adam is an adaptive optimiser that keeps running averages of past gradients and their squares to give each weight its own effective learning rate.

## Backpropagation

Backpropagation is the algorithm that computes the gradient of the loss with respect to every weight in the network efficiently. It applies the chain rule of calculus layer by layer, starting from the output and moving backwards towards the input. Each layer receives the gradient of the loss with respect to its outputs and uses it to compute the gradient with respect to its weights and its inputs. Because intermediate results are reused, backpropagation costs roughly the same as a forward pass.

## Overfitting and regularisation

Overfitting occurs when a model memorises the training data, including its noise, instead of learning patterns that generalise to new examples. An overfit model has a low training loss but a high validation loss. Regularisation refers to techniques that discourage overly complex models. Weight decay adds a penalty proportional to the size of the weights to the loss. Dropout randomly switches off a fraction of neurons during training, which forces the network to spread knowledge across many units. Early stopping halts training when the validation loss stops improving.
