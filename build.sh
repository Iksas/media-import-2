#!/bin/bash

# Delete ignored files
git clean -dfX ./mediaimport-2

# Check if there are any unstaged / uncommitted changes
if [[ $(git status -s ./mediaimport-2) ]]; then
    # Print error message and exit
    echo "ERROR: There are unstaged / uncommitted changes in the build directory."
    exit 1
fi

# Get the version number
version=$(sed 's/.*version": "\([^"]*\).*/\1/g' mediaimport-2/manifest.json)
echo "The plugin version is ${version}"

# Copy the license to the build folder
cp ./LICENSE ./mediaimport-2/LICENSE

# Delete previous builds
rm -f ./media_import_*.ankiaddon

# Create the Anki plugin
cd ./mediaimport-2
zip -r ../media_import_${version}.ankiaddon *
cd ..

# Delete the license from the build folder
rm ./mediaimport-2/LICENSE

echo "Successfully built 'media_import_${version}.ankiaddon'"
